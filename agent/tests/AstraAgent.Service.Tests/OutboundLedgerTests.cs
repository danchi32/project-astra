using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using AstraAgent.Service.Api;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3 · E3 Outbound Ledger: every request is written down, the bytes recorded are the
/// bytes sent, and no secret reaches the disk, above all a BitLocker recovery password.
/// </summary>
public sealed class OutboundLedgerTests : IDisposable
{
    const string Recovery = "123456-234567-345678-456789-567890-678901-789012-890123";
    readonly string _dir = Path.Combine(Path.GetTempPath(), "savio-ledger-" + Guid.NewGuid().ToString("N"));

    public void Dispose()
    {
        if (Directory.Exists(_dir)) Directory.Delete(_dir, true);
    }

    sealed class Stub(HttpStatusCode status) : HttpMessageHandler
    {
        public string? Received;
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage r, CancellationToken ct)
        {
            Received = r.Content is null ? null : await r.Content.ReadAsStringAsync(ct);
            return new HttpResponseMessage(status);
        }
    }

    (HttpClient Http, Stub Stub, OutboundLedger Ledger) Client(HttpStatusCode status = HttpStatusCode.OK)
    {
        var stub = new Stub(status);
        var ledger = new OutboundLedger(_dir);
        var http = new HttpClient(new OutboundLedgerHandler(ledger) { InnerHandler = stub }) { BaseAddress = new Uri("https://savio.test") };
        return (http, stub, ledger);
    }

    List<JsonObject> Lines() => Directory.GetFiles(_dir, "ledger-*.jsonl")
        .SelectMany(File.ReadAllLines).Select(l => JsonNode.Parse(l)!.AsObject()).ToList();

    string Raw() => string.Join("\n", Directory.GetFiles(_dir).Select(File.ReadAllText));

    [Fact]
    public async Task Every_request_is_written_down_as_sent()
    {
        var (http, stub, _) = Client();
        using var req = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/telemetry")
        {
            Content = JsonContent.Create(new { cpu = 12.5, apps = new[] { "Excel", "Chrome" } }),
        };
        req.Headers.Authorization = new("Bearer", "device-token-secret");
        await http.SendAsync(req);
        var sent = stub.Received!;
        await http.GetAsync("/api/v1/agent/browser-policy");

        var lines = Lines();
        Assert.Equal(2, lines.Count);
        Assert.Equal("/api/v1/agent/telemetry", lines[0]["path"]!.GetValue<string>());
        Assert.Equal(200, lines[0]["status"]!.GetValue<int>());
        Assert.Equal("Excel", lines[0]["body"]!["apps"]![0]!.GetValue<string>());
        Assert.Equal(sent.Length, lines[0]["bytes"]!.GetValue<long>());             // what went is what was recorded
        Assert.Equal(12.5, lines[0]["body"]!["cpu"]!.GetValue<double>());
        Assert.Null(lines[1]["body"]);
        Assert.DoesNotContain("device-token-secret", Raw());                        // headers are never written
    }

    [Fact]
    public async Task No_secret_reaches_the_disk()
    {
        var (http, stub, _) = Client();
        await http.PostAsJsonAsync("/api/v1/agent/bitlocker-keys",
            new { keys = new[] { new { drive = "C:", protector_id = "{x}", recovery_password = Recovery } } });
        await http.PostAsJsonAsync("/api/v1/agent/enroll",
            new { enrollment_token = "enrol-secret", hostname = "PC-1", nested = new { note = $"key {Recovery} here", password_hint = "pw" } });

        Assert.Contains(Recovery, stub.Received!);           // the backend still got what it needed
        var raw = Raw();
        Assert.DoesNotContain(Recovery, raw);
        Assert.DoesNotContain("enrol-secret", raw);
        var lines = Lines();
        Assert.Equal(OutboundLedger.NotRecorded, lines[0]["body"]!.GetValue<string>());   // the whole escrow body
        Assert.Equal("PC-1", lines[1]["body"]!["hostname"]!.GetValue<string>());
        Assert.Equal(OutboundLedger.NotRecorded, lines[1]["body"]!["nested"]!["note"]!.GetValue<string>());

        // Review C1: a generated password inside a task result's sentence.
        await http.PostAsJsonAsync("/api/v1/agent/tasks/1/result", new
        {
            success = true,
            output = "Reset done.\nTemporary password: Xk9#vQ2!pLm7\n\nOne-time password: Zz8$aa11 must be changed.",
        });
        Assert.Contains("Xk9#vQ2!pLm7", stub.Received!);
        Assert.DoesNotContain("Xk9#vQ2!pLm7", Raw());
        Assert.DoesNotContain("Zz8$aa11", Raw());
        Assert.Contains("Temporary password: [not recorded]", Lines()[^1]["body"]!["output"]!.GetValue<string>());
    }

    [Fact]
    public async Task A_failed_request_is_still_written_down_and_old_days_are_pruned()
    {
        Directory.CreateDirectory(_dir);
        var old = Path.Combine(_dir, $"ledger-{DateTime.UtcNow.AddDays(-30):yyyy-MM-dd}.jsonl");
        File.WriteAllText(old, "{}\n");

        var ledger = new OutboundLedger(_dir);
        var http = new HttpClient(new OutboundLedgerHandler(ledger) { InnerHandler = new Throwing() }) { BaseAddress = new Uri("https://savio.test") };
        await Assert.ThrowsAsync<HttpRequestException>(() => http.PostAsJsonAsync("/api/v1/agent/heartbeat", new { a = 1 }));

        var line = Assert.Single(Lines());
        Assert.Null(line["status"]);                        // never answered, but the data may have left
        Assert.False(File.Exists(old));
    }

    sealed class Throwing : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage r, CancellationToken ct) =>
            throw new HttpRequestException("offline");
    }

    [Fact]
    public void A_body_that_is_not_json_is_described_not_copied()
    {
        Assert.Equal("[not JSON, 5 bytes]", OutboundLedger.Redact("hello"u8.ToArray())!.GetValue<string>());
        Assert.Equal(OutboundLedger.NotRecorded, OutboundLedger.Redact(System.Text.Encoding.UTF8.GetBytes($"\"{Recovery}\""))!.GetValue<string>());
    }
}
