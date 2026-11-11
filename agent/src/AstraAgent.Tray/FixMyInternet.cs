using System;
using System.IO.Pipes;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace AstraAgent.Tray;

/// <summary>B2 — the Tray side of "Fix my internet". Works with no internet at all: it only
/// talks to SAVIO's own service on this PC, over a local pipe that accepts one word.</summary>
public static class FixMyInternet
{
    // Mirrors NetworkFixPipeServer.PipeName / Verb in the service.
    private const string PipeName = "SAVIO.FixMyInternet";
    private const string Verb = "fix";

    /// <summary>One sentence for the person: what was wrong and whether it was fixed.</summary>
    public static async Task<string> RunAsync(CancellationToken ct = default)
    {
        try
        {
            // Identification: whoever is on the other end may learn who we are, never act as us.
            await using var pipe = new NamedPipeClientStream(".", PipeName, PipeDirection.InOut,
                PipeOptions.Asynchronous, TokenImpersonationLevel.Identification);
            using (var connect = CancellationTokenSource.CreateLinkedTokenSource(ct))
            {
                connect.CancelAfter(TimeSpan.FromSeconds(5));
                await pipe.ConnectAsync(connect.Token);
            }
            // Pipe names are shared by every session on the PC, so another signed-in user could
            // create this one first and answer in SAVIO's name. The service's pipe is owned by
            // SYSTEM; anything else is not SAVIO.
            if (!OwnedBySystem(pipe))
                return "Something other than SAVIO answered, so nothing was run. Contact IT.";
            await pipe.WriteAsync(Encoding.UTF8.GetBytes(Verb), ct);
            await pipe.FlushAsync(ct);

            // The ladder can take a minute or two (waits after each step to see if it worked).
            using var read = CancellationTokenSource.CreateLinkedTokenSource(ct);
            read.CancelAfter(TimeSpan.FromMinutes(3));
            var buf = new byte[1024];
            var n = await pipe.ReadAsync(buf, read.Token);
            var reply = Encoding.UTF8.GetString(buf, 0, n).Trim();
            return reply.Length > 0 ? reply : "SAVIO checked the connection but had nothing to report.";
        }
        catch (OperationCanceledException)
        {
            return "SAVIO's background service didn't answer. Restart the PC, or contact IT.";
        }
        catch (Exception ex)
        {
            return $"Couldn't reach SAVIO's background service ({ex.GetType().Name}). Restart the PC, or contact IT.";
        }
    }

    private static bool OwnedBySystem(NamedPipeClientStream pipe)
    {
        try
        {
            var owner = pipe.GetAccessControl().GetOwner(typeof(SecurityIdentifier)) as SecurityIdentifier;
            return owner is not null && owner.IsWellKnown(WellKnownSidType.LocalSystemSid);
        }
        catch { return false; }
    }
}
