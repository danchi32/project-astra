using System;
using System.Runtime.InteropServices;

namespace AstraAgent.Service.Sessions;

/// <summary>P/Invoke surface for Windows Terminal Services, shared by the session collector
/// and the session actions.
///
/// LocalAccountManager and LoggedInUserResolver declare their own copies of some of these
/// and are deliberately left alone. Both are load-bearing, both are tested, and rewriting
/// working interop to remove duplication is how a signature quietly changes underneath
/// something that was working — the duplication costs a few lines and nothing else.</summary>
internal static class WtsNative
{
    // WTS_CONNECTSTATE_CLASS. Only the two interactive states matter to us; the rest
    // (Connected, ConnectQuery, Shadow, Idle, Listen, Reset, Down, Init) describe the
    // terminal-services transport rather than a person with a desktop.
    public const int WtsActive = 0;
    public const int WtsDisconnected = 4;

    // WTS_INFO_CLASS values we query.
    public const int WtsUserName = 5;
    public const int WtsWinStationName = 6;
    public const int WtsDomainName = 7;
    public const int WtsClientName = 10;
    public const int WtsSessionInfo = 24;   // returns WTSINFOW

    [StructLayout(LayoutKind.Sequential)]
    public struct WTS_SESSION_INFO
    {
        public int SessionId;
        [MarshalAs(UnmanagedType.LPWStr)] public string pWinStationName;
        public int State;
    }

    /// <summary>WTSINFOW. The fixed-width character arrays are not decoration: the struct is
    /// marshalled by size, so a wrong length here silently misaligns every field after it —
    /// the logon time would be read out of the middle of the user name. The constants are
    /// Windows': WINSTATIONNAME_LENGTH 32, DOMAIN_LENGTH 17, USERNAME_LENGTH 20 (+1).</summary>
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct WTSINFO
    {
        public int State;
        public int SessionId;
        public int IncomingBytes;
        public int OutgoingBytes;
        public int IncomingFrames;
        public int OutgoingFrames;
        public int IncomingCompressedBytes;
        public int OutgoingCompressedBytes;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string WinStationName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 17)] public string Domain;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 21)] public string UserName;
        public long ConnectTime;
        public long DisconnectTime;
        public long LastInputTime;
        public long LogonTime;
        public long CurrentTime;
    }

    [DllImport("wtsapi32.dll", SetLastError = true)]
    public static extern bool WTSEnumerateSessions(
        IntPtr hServer, int reserved, int version, ref IntPtr ppSessionInfo, out int pCount);

    [DllImport("wtsapi32.dll")]
    public static extern void WTSFreeMemory(IntPtr memory);

    [DllImport("wtsapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool WTSQuerySessionInformation(
        IntPtr hServer, int sessionId, int wtsInfoClass, out IntPtr ppBuffer, out int pBytesReturned);

    [DllImport("wtsapi32.dll", SetLastError = true)]
    public static extern bool WTSLogoffSession(IntPtr hServer, int sessionId, bool bWait);

    [DllImport("wtsapi32.dll", SetLastError = true)]
    public static extern bool WTSDisconnectSession(IntPtr hServer, int sessionId, bool bWait);

    [DllImport("wtsapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool WTSSendMessage(
        IntPtr hServer, int sessionId,
        string pTitle, int titleLength,
        string pMessage, int messageLength,
        int style, int timeout, out int pResponse, bool bWait);

    [DllImport("wtsapi32.dll", SetLastError = true)]
    public static extern bool WTSQueryUserToken(int sessionId, out IntPtr phToken);

    /// <summary>A queried string for one session, or empty. Every caller wants "the value or
    /// nothing" — the distinction between "the call failed" and "Windows returned an empty
    /// string" has never once mattered to anything above this.</summary>
    public static string QueryString(int sessionId, int infoClass)
    {
        if (!WTSQuerySessionInformation(IntPtr.Zero, sessionId, infoClass, out var buffer, out _))
            return string.Empty;
        try { return (Marshal.PtrToStringUni(buffer) ?? string.Empty).Trim(); }
        finally { if (buffer != IntPtr.Zero) WTSFreeMemory(buffer); }
    }

    /// <summary>The WTSINFOW record for a session, or null when it can't be read.</summary>
    public static WTSINFO? QueryInfo(int sessionId)
    {
        if (!WTSQuerySessionInformation(IntPtr.Zero, sessionId, WtsSessionInfo, out var buffer, out var size))
            return null;
        try
        {
            if (buffer == IntPtr.Zero || size < Marshal.SizeOf<WTSINFO>())
                return null;
            return Marshal.PtrToStructure<WTSINFO>(buffer);
        }
        catch { return null; }
        finally { if (buffer != IntPtr.Zero) WTSFreeMemory(buffer); }
    }

    /// <summary>Enumerates every session on this machine. Returns an empty list rather than
    /// throwing: telemetry runs every minute and a machine that momentarily cannot enumerate
    /// its sessions should push the rest of its telemetry, not lose the whole cycle.</summary>
    public static List<WTS_SESSION_INFO> Enumerate()
    {
        var result = new List<WTS_SESSION_INFO>();
        var ptr = IntPtr.Zero;
        try
        {
            if (!WTSEnumerateSessions(IntPtr.Zero, 0, 1, ref ptr, out var count))
                return result;
            var size = Marshal.SizeOf<WTS_SESSION_INFO>();
            var cursor = ptr;
            for (var i = 0; i < count; i++)
            {
                result.Add(Marshal.PtrToStructure<WTS_SESSION_INFO>(cursor));
                cursor += size;
            }
        }
        catch { /* best effort — see above */ }
        finally { if (ptr != IntPtr.Zero) WTSFreeMemory(ptr); }
        return result;
    }

    /// <summary>Console or RDP, decided from the WinStation name with the client name as a
    /// tiebreak.
    ///
    /// The station name is the honest answer ("Console", "RDP-Tcp#7"), but it is also the
    /// field most likely to be renamed by third-party terminal-services stacks — so a
    /// session that names itself nothing recognisable and has a remote client attached is
    /// treated as remote, because that is what it is.</summary>
    public static string ConnectionKind(string? stationName, string? clientName)
    {
        var station = (stationName ?? string.Empty).Trim();
        if (station.StartsWith("Console", StringComparison.OrdinalIgnoreCase))
            return "console";
        if (station.StartsWith("RDP", StringComparison.OrdinalIgnoreCase)
            || station.StartsWith("ICA", StringComparison.OrdinalIgnoreCase))
            return "rdp";
        return string.IsNullOrWhiteSpace(clientName) ? "console" : "rdp";
    }

    /// <summary>A FILETIME from WTSINFOW as a UTC instant, or null when Windows reported 0.
    ///
    /// Zero is common and is not a date: local console sessions frequently report no
    /// LastInputTime at all. Converting it anyway yields 1601-01-01, which then travels all
    /// the way to a portal that renders "signed in 424 years ago".</summary>
    public static DateTimeOffset? FromFileTime(long fileTime)
    {
        if (fileTime <= 0) return null;
        try { return DateTimeOffset.FromFileTime(fileTime).ToUniversalTime(); }
        catch { return null; }
    }
}
