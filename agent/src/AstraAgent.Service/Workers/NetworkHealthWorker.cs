using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using AstraAgent.Service.Net;

namespace AstraAgent.Service.Workers;

/// <summary>B1 — every minute, if SAVIO can't be reached, diagnose and try the offline ladder.
/// When the connection is back, upload what was done so it lands in the audit log.</summary>
public sealed class NetworkHealthWorker(
    NetworkDoctor doctor,
    IEnrollmentService enrollment,
    IAstraApiClient api,
    ILogger<NetworkHealthWorker> logger) : BackgroundService
{
    private static readonly TimeSpan Interval = TimeSpan.FromSeconds(60);
    // Give the machine time to finish booting and joining Wi-Fi before judging the network.
    private static readonly TimeSpan StartupGrace = TimeSpan.FromMinutes(2);
    internal const int UploadChunk = 200;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try { await Task.Delay(StartupGrace, stoppingToken); } catch (OperationCanceledException) { return; }
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                if (await doctor.BackendReachableAsync(stoppingToken))
                    await UploadJournalAsync(stoppingToken);
                else
                {
                    var outcome = await doctor.RunAsync("automatic", manual: false, stoppingToken);
                    if (outcome.Length > 0) logger.LogInformation("Offline self-heal: {Outcome}", outcome);
                }
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { return; }
            catch (Exception ex) { logger.LogWarning(ex, "Network health check failed"); }

            try { await Task.Delay(Interval, stoppingToken); } catch (OperationCanceledException) { return; }
        }
    }

    private async Task UploadJournalAsync(CancellationToken ct)
    {
        var entries = doctor.ReadJournal();
        if (entries.Count == 0) return;
        var token = await enrollment.GetDeviceTokenAsync(ct);
        if (token is null) return;
        // The backend takes at most 200 per request; one oversized upload used to fail forever
        // and keep every entry off the audit log. Send in chunks; keep only what wasn't accepted.
        for (var i = 0; i < entries.Count; i += UploadChunk)
        {
            if (!await api.PushOfflineEventsAsync(token, entries.Skip(i).Take(UploadChunk).ToList(), ct))
            {
                doctor.KeepJournal(entries.Skip(i));
                return;
            }
        }
        doctor.ClearJournal();
    }
}

/// <summary>B2 — the Tray's "Fix my internet". A named pipe with ONE verb and no parameters:
/// the person at the desk can ask the elevated service to run the same ladder, under the same
/// limits, and read back one sentence. Nothing else can be asked through it.</summary>
public sealed class NetworkFixPipeServer(NetworkDoctor doctor, ILogger<NetworkFixPipeServer> logger)
    : BackgroundService
{
    public const string PipeName = "SAVIO.FixMyInternet";
    public const string Verb = "fix";

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                // FirstPipeInstance: if anyone else already created this name (a squatter waiting
                // for the Tray), fail and log rather than share it with them.
                await using var pipe = NamedPipeServerStreamAcl.Create(PipeName, PipeDirection.InOut, 1,
                    PipeTransmissionMode.Byte, PipeOptions.Asynchronous | PipeOptions.FirstPipeInstance,
                    256, 1024, Security());
                await pipe.WaitForConnectionAsync(stoppingToken);

                // A client that connects and never writes would otherwise hold the only
                // instance until the service restarts — for every user on the PC.
                using var readTimeout = CancellationTokenSource.CreateLinkedTokenSource(stoppingToken);
                readTimeout.CancelAfter(TimeSpan.FromSeconds(2));
                var buf = new byte[16];
                int n;
                try { n = await pipe.ReadAsync(buf, readTimeout.Token); }
                catch (OperationCanceledException) when (!stoppingToken.IsCancellationRequested) { continue; }
                var reply = Encoding.UTF8.GetString(buf, 0, n).Trim() == Verb
                    ? await doctor.RunAsync("tray", manual: true, stoppingToken)
                    : "Unknown request.";
                await pipe.WriteAsync(Encoding.UTF8.GetBytes(reply), stoppingToken);
                await pipe.FlushAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { return; }
            catch (Exception ex)
            {
                logger.LogWarning(ex, "Fix-my-internet pipe error");
                try { await Task.Delay(1000, stoppingToken); } catch (OperationCanceledException) { return; }
            }
        }
    }

    /// <summary>Signed-in people may connect and talk; only SYSTEM owns the pipe. Remote (network)
    /// access is denied — this is for the person at this PC.</summary>
    internal static PipeSecurity Security()
    {
        var s = new PipeSecurity();
        // Owned by SYSTEM explicitly: the Tray checks the owner before it trusts the reply,
        // so a pipe created by anyone else is refused.
        s.SetOwner(new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null));
        s.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
            PipeAccessRights.FullControl, AccessControlType.Allow));
        s.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.InteractiveSid, null),
            PipeAccessRights.ReadWrite, AccessControlType.Allow));
        s.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.NetworkSid, null),
            PipeAccessRights.FullControl, AccessControlType.Deny));
        return s;
    }
}
