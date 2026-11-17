using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using AstraAgent.Service.Security;

namespace AstraAgent.Service.Api;

/// <summary>
/// Phase 3 · E3: the Outbound Ledger. A readable local copy of everything this agent sends to
/// SAVIO, so a customer's IT can check what leaves their PCs, line by line, without trusting
/// our word for it.
///
/// One JSON line per request: when, method, path, status, size, and the body. Kept 14 days in
/// <c>state\ledger\ledger-YYYY-MM-DD.jsonl</c> beside the install folder, a folder only SYSTEM
/// and Administrators can read. The bodies include things one person on a shared PC should not
/// read about another (the Tracker's activity, for one).
///
/// What is never written:
/// <list type="bullet">
/// <item>Headers, so never the device token.</item>
/// <item>The BitLocker escrow body: recovery passwords must not exist anywhere on disk in clear
/// text. The line says the call happened and how big it was.</item>
/// <item>Any property named like a password, token or secret, and any string shaped like a
/// BitLocker recovery password, wherever it appears. Defence in depth, not the rule.</item>
/// </list>
/// The ledger never stands in the way of a request: if it cannot write, the request still goes.
/// Past <see cref="MaxBodyBytesPerDay"/> in a day, lines keep coming but without bodies.
/// </summary>
public sealed class OutboundLedger
{
    public const int KeepDays = 14;
    public const long MaxBodyBytesPerDay = 20 * 1024 * 1024;
    public const string NotRecorded = "[not recorded]";

    static readonly string[] BodyNeverRecorded = ["/api/v1/agent/bitlocker-keys"];
    static readonly Regex SecretName = new("password|token|secret", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    static readonly Regex RecoveryPassword = new(@"\d{6}(-\d{6}){7}", RegexOptions.CultureInvariant);

    readonly string _dir;
    readonly bool _secure;
    readonly object _gate = new();
    DateOnly _day;
    long _bodyBytesToday;
    bool? _usable;

    /// <param name="dir">Null for the real folder, hardened with <see cref="SecureDirectory"/>.
    /// Tests pass a temp folder, which is used as it is.</param>
    public OutboundLedger(string? dir = null)
    {
        _secure = dir is null;
        _dir = dir ?? Path.Combine(SecureDirectory.StateRoot, "ledger");
    }

    public string Directory => _dir;

    public void Record(DateTime atUtc, string method, string path, int? status, long bytes, byte[]? body)
    {
        try
        {
            lock (_gate)
            {
                if (!Usable()) return;
                var day = DateOnly.FromDateTime(atUtc);
                var file = Path.Combine(_dir, $"ledger-{day:yyyy-MM-dd}.jsonl");
                if (day != _day)
                {
                    _day = day;
                    _bodyBytesToday = File.Exists(file) ? new FileInfo(file).Length : 0;
                    Prune(day);
                }

                var line = new JsonObject
                {
                    ["at"] = atUtc.ToString("O"),
                    ["method"] = method,
                    ["path"] = path,
                    ["status"] = status,
                    ["bytes"] = bytes,
                };
                if (body is { Length: > 0 })
                {
                    if (BodyNeverRecorded.Contains(path, StringComparer.OrdinalIgnoreCase))
                        line["body"] = NotRecorded;
                    else if (_bodyBytesToday + body.Length > MaxBodyBytesPerDay)
                        line["body"] = "[not recorded: today's ledger is full]";
                    else
                        line["body"] = Redact(body);
                }
                var text = line.ToJsonString() + "\n";
                File.AppendAllText(file, text, Encoding.UTF8);
                _bodyBytesToday += text.Length;
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            // A full disk or a locked file must not stop the agent talking to SAVIO.
        }
    }

    /// <summary>The body as JSON with secrets replaced; a non-JSON body is described, not copied.</summary>
    internal static JsonNode? Redact(byte[] body)
    {
        JsonNode? node;
        try { node = JsonNode.Parse(body); }
        catch (JsonException) { return $"[not JSON, {body.Length} bytes]"; }
        if (IsRecovery(node)) return NotRecorded;
        Scrub(node);
        return node;
    }

    /// <summary>Replaces secrets in place; only a changed slot is reassigned.</summary>
    static void Scrub(JsonNode? node)
    {
        switch (node)
        {
            case JsonObject o:
                foreach (var name in o.Select(p => p.Key).ToList())
                {
                    var child = o[name];
                    if (child is null) continue;
                    if (SecretName.IsMatch(name) || IsRecovery(child)) o[name] = NotRecorded;
                    else Scrub(child);
                }
                break;
            case JsonArray a:
                for (var i = 0; i < a.Count; i++)
                {
                    if (IsRecovery(a[i])) a[i] = NotRecorded;
                    else Scrub(a[i]);
                }
                break;
        }
    }

    static bool IsRecovery(JsonNode? n) =>
        n is JsonValue v && v.TryGetValue(out string? s) && RecoveryPassword.IsMatch(s);

    bool Usable()
    {
        if (_usable is { } known) return known;
        try
        {
            if (_secure) SecureDirectory.Ensure(_dir);
            else System.IO.Directory.CreateDirectory(_dir);
            _usable = true;
        }
        catch (Exception)
        {
            // Fails closed: a folder that could not be locked down is not written to.
            _usable = false;
        }
        return _usable.Value;
    }

    void Prune(DateOnly today)
    {
        foreach (var f in System.IO.Directory.EnumerateFiles(_dir, "ledger-*.jsonl"))
        {
            var name = Path.GetFileNameWithoutExtension(f);
            if (DateOnly.TryParseExact(name["ledger-".Length..], "yyyy-MM-dd", out var d) && d < today.AddDays(-KeepDays))
                File.Delete(f);
        }
    }
}

/// <summary>Puts every request the API client sends through the <see cref="OutboundLedger"/>.</summary>
public sealed class OutboundLedgerHandler(OutboundLedger ledger) : DelegatingHandler
{
    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
    {
        byte[]? body = null;
        if (request.Content is not null)
        {
            // Buffered once: the bytes recorded are exactly the bytes sent.
            await request.Content.LoadIntoBufferAsync();
            body = await request.Content.ReadAsByteArrayAsync(ct);
        }
        HttpResponseMessage? response = null;
        try
        {
            response = await base.SendAsync(request, ct);
            return response;
        }
        finally
        {
            ledger.Record(DateTime.UtcNow, request.Method.Method, request.RequestUri?.AbsolutePath ?? "",
                          response is null ? null : (int)response.StatusCode, body?.LongLength ?? 0, body);
        }
    }
}
