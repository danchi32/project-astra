using System.IO.Pipes;
using System.Text;
using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;

namespace AstraAgent.Service.Guard;

/// <summary>
/// Phase 3c · C3b: the tray's "Ask IT to allow USB writing". A local pipe with two requests:
/// <c>status</c> (what the menu should show) and <c>request:&lt;reason&gt;</c> (send it to IT). The
/// reason is a code from a fixed list, never typed text. Who asks is taken from Windows (the
/// pipe client's own process token, as for the browser's events), never from the message.
/// Same rules as Fix-my-internet: owned by SYSTEM, signed-in people may connect, no network.
/// </summary>
public sealed class UsbRequestPipeServer(
    BrowserPolicyWorker policy,
    IEnrollmentService enrollment,
    IAstraApiClient api,
    ILogger<UsbRequestPipeServer> logger) : BackgroundService
{
    public const string PipeName = "SAVIO.UsbRequest";
    public static readonly string[] Reasons = ["client_or_ca", "backup", "presentation", "other"];

    /// <summary>Tests use their own name and no ACL: only SYSTEM may create a SYSTEM-owned pipe.</summary>
    internal string Name { get; init; } = PipeName;
    internal Func<PipeSecurity?> Security { get; init; } = Workers.NetworkFixPipeServer.Security;
    internal Func<NamedPipeServerStream, string?> Account { get; init; } = GuardEventPipeServer.ClientAccount;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await using var pipe = Create();
                await pipe.WaitForConnectionAsync(stoppingToken);
                await HandleAsync(pipe, DateTime.UtcNow, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { return; }
            catch (Exception ex)
            {
                logger.LogWarning(ex, "USB request pipe error");
                try { await Task.Delay(1000, stoppingToken); } catch (OperationCanceledException) { return; }
            }
        }
    }

    internal NamedPipeServerStream Create()
    {
        var options = PipeOptions.Asynchronous | PipeOptions.FirstPipeInstance;
        var security = Security();
        return security is null
            ? new NamedPipeServerStream(Name, PipeDirection.InOut, 1, PipeTransmissionMode.Byte, options, 256, 1024)
            : NamedPipeServerStreamAcl.Create(Name, PipeDirection.InOut, 1, PipeTransmissionMode.Byte, options, 256, 1024, security);
    }

    internal async Task HandleAsync(NamedPipeServerStream pipe, DateTime nowUtc, CancellationToken ct)
    {
        string message;
        using (var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct))
        {
            // A client that connects and says nothing holds up nobody for long.
            timeout.CancelAfter(TimeSpan.FromSeconds(2));
            var buf = new byte[64];
            try { message = Encoding.UTF8.GetString(buf, 0, await pipe.ReadAsync(buf, timeout.Token)).Trim(); }
            catch (OperationCanceledException) when (!ct.IsCancellationRequested) { return; }
        }
        var reply = await AnswerAsync(message, () => Account(pipe), nowUtc, ct);
        await pipe.WriteAsync(Encoding.UTF8.GetBytes(reply), ct);
        await pipe.FlushAsync(ct);
    }

    /// <summary>The reply to one request. Status: "off" (not in that mode), "closed" (read-only,
    /// can ask), or "open:&lt;UTC end&gt;". Request: one sentence for the person.</summary>
    internal async Task<string> AnswerAsync(string message, Func<string?> account, DateTime nowUtc, CancellationToken ct)
    {
        var p = policy.Current;
        var onRequest = p is { UsbMode: "on_request" };
        var until = policy.UsbWriteUntil;
        if (message == "status")
            return !onRequest ? "off" : until > nowUtc ? $"open:{until.Value:O}" : "closed";

        if (!message.StartsWith("request:", StringComparison.Ordinal) || !Reasons.Contains(message["request:".Length..]))
            return "Unknown request.";
        if (!onRequest)
            return "Your organization does not take USB requests on this PC.";
        if (until > nowUtc)
            return $"USB writing is already allowed until {until.Value.ToLocalTime():t}.";
        var user = account();
        if (string.IsNullOrEmpty(user) || user.Length > 256)
            return "SAVIO could not tell who is asking, so nothing was sent. Contact IT.";
        var token = await enrollment.GetDeviceTokenAsync(ct);
        if (token is null)
            return "This PC is not connected to SAVIO yet. Contact IT.";
        return await api.RequestUsbWriteAsync(token, user, message["request:".Length..], ct) switch
        {
            >= 200 and < 300 => "Request sent to IT. When they approve it, USB writing opens within a minute.",
            409 => "Your organization does not take USB requests on this PC right now.",
            0 => "SAVIO could not reach the server. Try again in a few minutes, or contact IT.",
            _ => "The request could not be sent. Contact IT.",
        };
    }
}
