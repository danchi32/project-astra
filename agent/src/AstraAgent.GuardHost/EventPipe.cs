using System.IO.Pipes;
using System.Security.Principal;
using AstraAgent.Guard;

namespace AstraAgent.GuardHost;

/// <summary>
/// Phase 3 · E3: hands one event to the SAVIO service over its local pipe.
///
/// The host runs as the signed-in person, so the service learns who it was from Windows
/// (Identification level: it may read our identity, never act as us). Pipe names are shared by
/// every session on the PC, so before writing, the host checks the pipe belongs to SYSTEM.
/// Someone else's pipe gets nothing. Best effort: if the service is not there the event is
/// dropped, and the extension still has its own local copy.
/// </summary>
public static class EventPipe
{
    // Mirrors GuardEventPipeServer.PipeName in the service.
    public const string PipeName = "SAVIO.GuardEvents";

    public static async Task<bool> SendAsync(GuardEvent e, CancellationToken ct)
    {
        try
        {
            await using var pipe = new NamedPipeClientStream(".", PipeName, PipeDirection.Out,
                PipeOptions.Asynchronous, TokenImpersonationLevel.Identification);
            using (var connect = CancellationTokenSource.CreateLinkedTokenSource(ct))
            {
                connect.CancelAfter(TimeSpan.FromSeconds(2));
                await pipe.ConnectAsync(connect.Token);
            }
            if (!OwnedBySystem(pipe)) return false;
            await pipe.WriteAsync(e.ToJson(), ct);
            await pipe.FlushAsync(ct);
            return true;
        }
        catch (Exception ex) when (ex is IOException or OperationCanceledException or TimeoutException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    static bool OwnedBySystem(NamedPipeClientStream pipe)
    {
        if (!OperatingSystem.IsWindows()) return false;
        try
        {
            var owner = pipe.GetAccessControl().GetOwner(typeof(SecurityIdentifier)) as SecurityIdentifier;
            return owner is not null && owner.IsWellKnown(WellKnownSidType.LocalSystemSid);
        }
        catch (Exception) { return false; }
    }
}
