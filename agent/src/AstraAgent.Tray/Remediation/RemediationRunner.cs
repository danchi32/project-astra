using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using AstraAgent.Service.Api;
using AstraAgent.Service.Security;
using AstraAgent.Service.Workers;

namespace AstraAgent.Tray.Remediation;

/// <summary>Background loop that claims approved remediation tasks for this device and
/// executes them via the allowlisted RemediationExecutor, reporting each result.
/// Writes a diagnostic log to %LocalAppData%\Astra\agent-remediation.log.</summary>
public sealed class RemediationRunner : IDisposable
{
    // 30s, not 10s: this poll is the single largest source of agent traffic (6 of the
    // ~10 requests/minute a device makes) and almost always returns nothing. The chat
    // now posts "Working on it" the moment a task is claimed, so the user sees progress
    // rather than silence while waiting for the next tick.
    private static readonly TimeSpan PollInterval = TimeSpan.FromSeconds(30);
    // A failing poll doubles its wait up to this, like the Service's workers. It used to retry
    // every 30s whatever came back, and append a log line each time.
    private static readonly TimeSpan MaxBackoff = TimeSpan.FromMinutes(15);

    private readonly HttpClient _http;
    private readonly ITokenStore _store;
    private readonly RemediationExecutor _executor = new();
    private readonly CancellationTokenSource _cts = new();
    private readonly string _logPath;
    private Task? _loop;

    public RemediationRunner(string serverUrl, ITokenStore store, string? proxyUrl = null)
    {
        _http = new HttpClient(AstraAgent.Service.Net.ProxyHttp.CreateHandler(proxyUrl))
        {
            BaseAddress = new Uri(serverUrl), Timeout = TimeSpan.FromSeconds(60),
        };
        _store = store;
        var dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Astra");
        _logPath = Path.Combine(dir, "agent-remediation.log");
        Log($"RemediationRunner created. server={serverUrl}");
    }

    public void Start()
    {
        Log("RemediationRunner loop starting.");
        _loop = Task.Run(() => LoopAsync(_cts.Token));
    }

    private void Log(string message)
    {
        var line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} {message}";
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_logPath)!);
            File.AppendAllText(_logPath, line + Environment.NewLine);
        }
        catch { /* logging is best-effort */ }
        Console.WriteLine("[remediation] " + message);
    }

    private async Task LoopAsync(CancellationToken ct)
    {
        var failures = 0;
        var dormant = false;
        while (!ct.IsCancellationRequested)
        {
            // The Service records an inactive organization in the registry (SubscriptionState).
            // While it says so, don't call the backend at all: this poll was most of an expired
            // device's traffic. It is re-read every interval, so polling resumes as soon as the
            // Service's hourly probe finds the organization active again.
            var nowDormant = SubscriptionState.ReadFromRegistry();
            if (nowDormant != dormant)
            {
                Log(nowDormant
                    ? "Organization inactive; pausing task polling."
                    : "Organization active again; resuming task polling.");
                dormant = nowDormant;
                failures = 0;
            }

            if (!dormant)
            {
                try { failures = await PollOnceAsync(ct) ? 0 : failures + 1; }
                catch (OperationCanceledException) { break; }
                catch (Exception ex) { failures++; Log("Poll failed: " + ex.Message); }
            }

            var delay = dormant
                ? PollInterval
                : BackoffCalculator.NextDelay(failures, PollInterval, MaxBackoff);
            try { await Task.Delay(delay, ct); }
            catch (OperationCanceledException) { break; }
        }
    }

    /// <returns>False when the backend refused or answered with an error, so the loop backs
    /// off; true otherwise (including "not enrolled yet", which made no request).</returns>
    private async Task<bool> PollOnceAsync(CancellationToken ct)
    {
        var token = _store.Load();
        if (token is null)
        {
            Log("No device credential yet — not enrolled? Skipping.");
            return true;
        }

        List<AgentTask>? tasks;
        using (var request = new HttpRequestMessage(HttpMethod.Get, "/api/v1/agent/tasks"))
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var response = await _http.SendAsync(request, ct);
            if (!response.IsSuccessStatusCode)
            {
                Log($"GET /api/v1/agent/tasks -> {(int)response.StatusCode} {response.StatusCode}");
                return false;
            }
            tasks = await response.Content.ReadFromJsonAsync<List<AgentTask>>(ct);
        }
        if (tasks is null || tasks.Count == 0)
            return true;  // quiet on the common "nothing to do" case

        Log($"Claimed {tasks.Count} task(s).");
        foreach (var task in tasks)
        {
            Log($"Executing {task.ActionId} (params: {(task.Params is null ? "-" : string.Join(",", task.Params.Keys))})");
            var (success, output) = await _executor.ExecuteAsync(task.ActionId, task.Params, ct);
            Log($"  -> success={success}: {output}");
            using var report = new HttpRequestMessage(
                HttpMethod.Post, $"/api/v1/agent/tasks/{task.Id}/result")
            {
                Content = JsonContent.Create(new ResultBody(success, output)),
            };
            report.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var reportResponse = await _http.SendAsync(report, ct);
            Log($"  reported result -> {(int)reportResponse.StatusCode}");
        }
        return true;
    }

    public void Dispose()
    {
        _cts.Cancel();
        try { _loop?.Wait(TimeSpan.FromSeconds(2)); }
        catch { /* ignore shutdown races */ }
        _cts.Dispose();
        _http.Dispose();
    }

    private sealed record AgentTask(
        [property: JsonPropertyName("id")] Guid Id,
        [property: JsonPropertyName("action_id")] string ActionId,
        [property: JsonPropertyName("params")] Dictionary<string, string>? Params);

    private sealed record ResultBody(
        [property: JsonPropertyName("success")] bool Success,
        [property: JsonPropertyName("output")] string Output);
}
