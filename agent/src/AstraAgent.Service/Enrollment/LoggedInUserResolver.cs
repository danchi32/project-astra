using System.Runtime.InteropServices;

namespace AstraAgent.Service.Enrollment;

/// <summary>Resolves the interactive console user from the service session (session 0)
/// via the WTS APIs — the service itself never runs as that user.</summary>
public static class LoggedInUserResolver
{
    private const uint NoActiveSession = 0xFFFFFFFF;

    public static string? GetConsoleUser()
    {
        var sessionId = WTSGetActiveConsoleSessionId();
        if (sessionId == NoActiveSession)
            return null;

        var user = QuerySessionString(sessionId, WtsInfoClass.WTSUserName);
        if (string.IsNullOrEmpty(user))
            return null;

        var domain = QuerySessionString(sessionId, WtsInfoClass.WTSDomainName);
        return string.IsNullOrEmpty(domain) ? user : $"{domain}\\{user}";
    }

    private static string? QuerySessionString(uint sessionId, WtsInfoClass infoClass)
    {
        if (!WTSQuerySessionInformation(IntPtr.Zero, sessionId, infoClass, out var buffer, out _))
            return null;
        try
        {
            return Marshal.PtrToStringUni(buffer);
        }
        finally
        {
            WTSFreeMemory(buffer);
        }
    }

    private enum WtsInfoClass
    {
        WTSUserName = 5,
        WTSDomainName = 7,
    }

    [DllImport("kernel32.dll")]
    private static extern uint WTSGetActiveConsoleSessionId();

    [DllImport("wtsapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool WTSQuerySessionInformation(
        IntPtr server, uint sessionId, WtsInfoClass infoClass, out IntPtr buffer, out uint bytesReturned);

    [DllImport("wtsapi32.dll")]
    private static extern void WTSFreeMemory(IntPtr buffer);
}
