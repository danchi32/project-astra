using AstraAgent.Service.Security;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using AstraAgent.Service.Remediation;
using Microsoft.Extensions.Options;

namespace AstraAgent.Service.Net;

/// <summary>Offline self-heal (B1/B2): when this PC can't reach SAVIO, work out why and try the
/// safe, automatic-tier network fixes — with no server involved, because there may be none.
///
/// Only three steps exist, each one the agent already runs on request: flush DNS, renew the
/// IP lease, restart the adapter. Nothing approval-tier or admin-only ever runs offline: there
/// is nobody to approve it. Every step is journalled to disk and uploaded to the audit log the
/// next time the PC is back online.</summary>
public enum Diagnosis
{
    Healthy,            // SAVIO reachable — nothing to do
    BackendOnlyDown,    // the internet works; only SAVIO's server is unreachable — not ours to fix
    NoAddress,          // no usable IPv4 (none, or 169.254.x self-assigned)
    GatewayUnreachable, // has an address, but the router doesn't answer
    DnsFailing,         // the internet answers by IP, names don't resolve
    NoInternet,         // router answers, nothing beyond it does — usually the ISP
}

public enum FixStep { FlushDns, RenewIp, RestartAdapter }

public sealed record Probe(bool HasUsableAddress, bool GatewayReachable, bool InternetByIp,
    bool DnsWorks, bool BackendReachable);

public sealed record JournalEntry(DateTimeOffset At, string Trigger, string Diagnosis,
    string? Step, bool? StepOk, string? Output, bool FixedAfter);

public static class NetworkRules
{
    public static Diagnosis Diagnose(Probe p)
    {
        if (p.BackendReachable) return Diagnosis.Healthy;
        if (!p.HasUsableAddress) return Diagnosis.NoAddress;
        if (!p.GatewayReachable && !p.InternetByIp) return Diagnosis.GatewayUnreachable;
        if (p.InternetByIp && !p.DnsWorks) return Diagnosis.DnsFailing;
        if (p.InternetByIp && p.DnsWorks) return Diagnosis.BackendOnlyDown;
        return Diagnosis.NoInternet;
    }

    /// <summary>Cheapest first; the run stops at the first step after which SAVIO answers.</summary>
    public static IReadOnlyList<FixStep> Ladder(Diagnosis d) => d switch
    {
        Diagnosis.NoAddress => [FixStep.RenewIp, FixStep.RestartAdapter],
        Diagnosis.GatewayUnreachable => [FixStep.RenewIp, FixStep.RestartAdapter],
        Diagnosis.DnsFailing => [FixStep.FlushDns, FixStep.RenewIp],
        // The fault is upstream; only the one step that can't make anything worse.
        Diagnosis.NoInternet => [FixStep.FlushDns],
        _ => [],
    };
}

/// <summary>How often the ladder may run. A broken network must not turn into an agent that
/// restarts the adapter every minute and makes everything worse.</summary>
public sealed class FixLimiter(Func<DateTimeOffset> now)
{
    public const int MaxLaddersPerHour = 3;
    public static readonly TimeSpan AdapterRestartGap = TimeSpan.FromHours(1);
    public static readonly TimeSpan ManualGap = TimeSpan.FromMinutes(2);
    /// <summary>Clicks from the Tray get their own hourly budget: the 2-minute gap alone still
    /// allowed ~30 runs an hour, each able to release every adapter's lease.</summary>
    public const int MaxManualPerHour = 6;

    private readonly List<DateTimeOffset> _ladders = [];
    private readonly List<DateTimeOffset> _manuals = [];
    private DateTimeOffset? _lastAdapterRestart;
    private DateTimeOffset? _lastManual;
    private readonly object _lock = new();

    public string? RefuseLadder(bool manual)
    {
        lock (_lock)
        {
            var t = now();
            _ladders.RemoveAll(x => t - x > TimeSpan.FromHours(1));
            _manuals.RemoveAll(x => t - x > TimeSpan.FromHours(1));
            if (manual && _lastManual is { } m && t - m < ManualGap)
                return "A network repair just ran — give it a couple of minutes before trying again.";
            if (manual && _manuals.Count >= MaxManualPerHour)
                return "Network repair has already run several times this hour. If it still isn't working, contact IT.";
            if (!manual && _ladders.Count >= MaxLaddersPerHour)
                return "Automatic network repair already ran 3 times this hour; waiting before trying again.";
            if (manual) { _manuals.Add(t); _lastManual = t; }
            else _ladders.Add(t);
            return null;
        }
    }

    public bool MayRestartAdapter()
    {
        lock (_lock)
        {
            var t = now();
            if (_lastAdapterRestart is { } r && t - r < AdapterRestartGap) return false;
            _lastAdapterRestart = t;
            return true;
        }
    }
}

/// <summary>Runs probes and the ladder. One instance, shared by the background worker and the
/// Tray's "Fix my internet" pipe, so the two can never run fixes at the same time.</summary>
public sealed class NetworkDoctor
{
    private readonly SemaphoreSlim _running = new(1, 1);
    private readonly FixLimiter _limiter;
    private readonly string _journalPath;
    private readonly Func<CancellationToken, Task<bool>> _backendReachable;
    private readonly ILogger<NetworkDoctor> _logger;

    public NetworkDoctor(IOptions<AgentOptions> options, ILogger<NetworkDoctor> logger)
        : this(logger, BackendProbe(options.Value.ServerUrl, options.Value.ProxyUrl), JournalPathDefault(),
               new FixLimiter(() => DateTimeOffset.UtcNow))
    {
        _hardenJournalDir = true;
    }

    private readonly bool _hardenJournalDir;
    /// <summary>Keep the newest this many entries: a device offline for days must not grow the
    /// file without bound, and the backend accepts at most 200 per upload.</summary>
    internal const int MaxJournalEntries = 1000;

    internal NetworkDoctor(ILogger<NetworkDoctor> logger, Func<CancellationToken, Task<bool>> backendReachable,
        string journalPath, FixLimiter limiter)
    {
        _logger = logger;
        _backendReachable = backendReachable;
        _journalPath = journalPath;
        _limiter = limiter;
    }

    public string JournalPath => _journalPath;

    public Task<bool> BackendReachableAsync(CancellationToken ct) => _backendReachable(ct);

    /// <summary>Diagnose and, if allowed, repair. Returns a sentence for a person to read.</summary>
    public async Task<string> RunAsync(string trigger, bool manual, CancellationToken ct,
        Func<FixStep, (bool, string)>? runStep = null)
    {
        if (!await _running.WaitAsync(TimeSpan.Zero, ct))
            return "A network repair is already running.";
        try
        {
            var diagnosis = NetworkRules.Diagnose(await ProbeAsync(ct));
            if (diagnosis == Diagnosis.Healthy)
                return manual ? "Your internet connection looks fine — SAVIO can reach its server." : "";
            if (diagnosis == Diagnosis.BackendOnlyDown)
                return "Your internet works; only SAVIO's server isn't answering right now. Nothing to fix on this PC.";

            var refusal = _limiter.RefuseLadder(manual);
            if (refusal is not null) return refusal;

            runStep ??= RunStep;
            foreach (var step in NetworkRules.Ladder(diagnosis))
            {
                if (step == FixStep.RestartAdapter && !_limiter.MayRestartAdapter())
                {
                    Journal(new(DateTimeOffset.UtcNow, trigger, diagnosis.ToString(), step.ToString(), null,
                        "skipped: the adapter was restarted less than an hour ago", false));
                    continue;
                }
                var (ok, output) = runStep(step);
                await Task.Delay(TimeSpan.FromSeconds(step == FixStep.FlushDns ? 2 : 8), ct);
                var fixedNow = await _backendReachable(ct);
                Journal(new(DateTimeOffset.UtcNow, trigger, diagnosis.ToString(), step.ToString(), ok,
                    Trim(output), fixedNow));
                if (fixedNow) return $"Fixed: {Describe(diagnosis)} — {Plain(step)} brought the connection back.";
            }
            return $"Couldn't fix it from this PC: {Describe(diagnosis)}. "
                 + (diagnosis == Diagnosis.NoInternet
                     ? "The router answers but nothing beyond it does — check with your internet provider."
                     : "Check the cable or Wi-Fi, or restart the router.");
        }
        finally
        {
            _running.Release();
        }
    }

    internal static string Describe(Diagnosis d) => d switch
    {
        Diagnosis.NoAddress => "the PC had no network address",
        Diagnosis.GatewayUnreachable => "the router wasn't answering",
        Diagnosis.DnsFailing => "website names weren't resolving (DNS)",
        Diagnosis.NoInternet => "there was no internet beyond the router",
        _ => d.ToString(),
    };

    private static string Plain(FixStep s) => s switch
    {
        FixStep.FlushDns => "clearing the DNS cache",
        FixStep.RenewIp => "renewing the network address",
        _ => "restarting the network adapter",
    };

    private static (bool, string) RunStep(FixStep step) => step switch
    {
        FixStep.FlushDns => FlushDns(),
        FixStep.RenewIp => BasicDiagnostics.RenewIpAddress(),
        _ => NetworkRemediation.RestartAdapter(),
    };

    private static (bool, string) FlushDns()
    {
        try
        {
            var psi = new ProcessStartInfo("ipconfig.exe", "/flushdns")
            { UseShellExecute = false, RedirectStandardOutput = true, CreateNoWindow = true };
            using var p = Process.Start(psi)!;
            var o = p.StandardOutput.ReadToEnd();
            p.WaitForExit(15000);
            return (p.ExitCode == 0, o.Trim());
        }
        catch (Exception ex) { return (false, ex.Message); }
    }

    // ── journal ──────────────────────────────────────────────────────────────

    private static readonly JsonSerializerOptions JsonOpts = new(JsonSerializerDefaults.Web);

    internal void Journal(JournalEntry e)
    {
        try
        {
            var dir = Path.GetDirectoryName(_journalPath)!;
            // SYSTEM appends, reads and deletes this file: its folder must be one no standard
            // user can create, own or swap for a junction (fails closed — no journal then).
            if (_hardenJournalDir) SecureDirectory.Ensure(dir);
            else Directory.CreateDirectory(dir);
            File.AppendAllText(_journalPath, JsonSerializer.Serialize(e, JsonOpts) + Environment.NewLine);
            var lines = File.ReadAllLines(_journalPath);
            if (lines.Length > MaxJournalEntries)
                File.WriteAllLines(_journalPath, lines[^MaxJournalEntries..]);
        }
        catch (Exception ex) { _logger.LogWarning(ex, "Could not write the offline journal"); }
    }

    public IReadOnlyList<JournalEntry> ReadJournal()
    {
        try
        {
            if (!File.Exists(_journalPath)) return [];
            // One bad line must not hide every good one (or block uploads for good).
            var entries = new List<JournalEntry>();
            foreach (var l in File.ReadAllLines(_journalPath).Where(l => l.Length > 0))
            {
                try { if (JsonSerializer.Deserialize<JournalEntry>(l, JsonOpts) is { } e) entries.Add(e); }
                catch (JsonException) { /* skipped */ }
            }
            return entries;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Offline journal unreadable; discarding it");
            return [];
        }
    }

    /// <summary>Rewrite the journal with only `remaining` (what an upload didn't get to).</summary>
    public void KeepJournal(IEnumerable<JournalEntry> remaining)
    {
        try { File.WriteAllLines(_journalPath, remaining.Select(e => JsonSerializer.Serialize(e, JsonOpts))); }
        catch (Exception ex) { _logger.LogWarning(ex, "Could not rewrite the offline journal"); }
    }

    public void ClearJournal()
    {
        try { File.Delete(_journalPath); } catch { /* next upload retries */ }
    }

    private static string Trim(string s) => s.Length <= 300 ? s : s[..300];

    // Under the install root, not C:\ProgramData (where any user may create the folder first).
    private static string JournalPathDefault() => Path.Combine(SecureDirectory.StateRoot, "offline-journal.jsonl");

    // ── probes ───────────────────────────────────────────────────────────────

    /// <summary>"Can SAVIO be reached" the way the agent really reaches it: an HTTP request
    /// through the same proxy handler as every API call. A raw TCP connect ignored the proxy,
    /// so a proxy-only office looked permanently offline — the ladder kept restarting adapters
    /// and the journal never uploaded. Any HTTP answer, even an error status, means reachable.</summary>
    private static Func<CancellationToken, Task<bool>> BackendProbe(string serverUrl, string? proxyUrl)
    {
        if (!Uri.TryCreate(serverUrl, UriKind.Absolute, out var u)) return _ => Task.FromResult(false);
        var http = new HttpClient(ProxyHttp.CreateHandler(proxyUrl)) { Timeout = TimeSpan.FromSeconds(8) };
        var health = new Uri(u, "/health");
        return async ct =>
        {
            try
            {
                using var resp = await http.GetAsync(health, HttpCompletionOption.ResponseHeadersRead, ct);
                return true;
            }
            catch { return false; }
        };
    }

    private async Task<Probe> ProbeAsync(CancellationToken ct)
    {
        var backend = await _backendReachable(ct);
        if (backend) return new Probe(true, true, true, true, true);

        var nics = NetworkInterface.GetAllNetworkInterfaces()
            .Where(n => n.OperationalStatus == OperationalStatus.Up
                        && n.NetworkInterfaceType is not (NetworkInterfaceType.Loopback or NetworkInterfaceType.Tunnel))
            .Select(n => n.GetIPProperties()).ToList();
        var hasAddress = nics.Any(p => p.UnicastAddresses.Any(a =>
            a.Address.AddressFamily == AddressFamily.InterNetwork && !a.Address.ToString().StartsWith("169.254.")));
        var gateway = nics.SelectMany(p => p.GatewayAddresses).Select(g => g.Address)
            .FirstOrDefault(a => a.AddressFamily == AddressFamily.InterNetwork && !a.Equals(IPAddress.Any));

        var gatewayOk = false;
        if (gateway is not null)
        {
            try { gatewayOk = (await new Ping().SendPingAsync(gateway, 1500)).Status == IPStatus.Success; }
            catch { /* treated as unreachable */ }
        }
        var internetByIp = await TcpReachable("1.1.1.1", 443, ct) || await TcpReachable("8.8.8.8", 443, ct);
        var dnsOk = false;
        try
        {
            var lookup = Dns.GetHostAddressesAsync("www.msftconnecttest.com", ct);
            dnsOk = await Task.WhenAny(lookup, Task.Delay(3000, ct)) == lookup && lookup.Result.Length > 0;
        }
        catch { /* treated as failing */ }

        return new Probe(hasAddress, gatewayOk, internetByIp, dnsOk, false);
    }

    private static async Task<bool> TcpReachable(string host, int port, CancellationToken ct)
    {
        try
        {
            using var c = new TcpClient();
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct);
            timeout.CancelAfter(TimeSpan.FromSeconds(4));
            await c.ConnectAsync(host, port, timeout.Token);
            return true;
        }
        catch { return false; }
    }
}
