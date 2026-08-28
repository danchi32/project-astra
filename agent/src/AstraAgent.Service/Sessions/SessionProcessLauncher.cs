using System;
using System.Runtime.InteropServices;

namespace AstraAgent.Service.Sessions;

/// <summary>Starts a process inside another user's session, as that user.
///
/// This exists for exactly one caller today — locking a workstation, which has no API and can
/// only be done by running LockWorkStation inside the session that is to be locked. It is
/// deliberately NOT a general "run a command as the user" facility: the caller passes an
/// executable and arguments that are constants in ASTRA's own source, never anything that
/// arrived from the network. If that ever changes, this becomes the most dangerous class in
/// the agent, and the allowlist that keeps the rest of the remediation path safe would have
/// to be extended to cover it.
///
/// The dance is the standard one and every step is load-bearing:
///   1. WTSQueryUserToken   — the session's own token (needs LocalSystem);
///   2. DuplicateTokenEx    — a primary token; the queried one is impersonation-only and
///                            CreateProcessAsUser refuses it;
///   3. CreateEnvironmentBlock — the user's environment, so the process sees their profile
///                            rather than LocalSystem's;
///   4. lpDesktop "winsta0\\default" — without it the process starts on the service window
///                            station, where there is no visible desktop and LockWorkStation
///                            has nothing to lock.</summary>
internal static class SessionProcessLauncher
{
    public static (bool Ok, string Detail) Run(int sessionId, string exeName, string arguments)
    {
        var userToken = IntPtr.Zero;
        var primaryToken = IntPtr.Zero;
        var environment = IntPtr.Zero;
        try
        {
            if (!WtsNative.WTSQueryUserToken(sessionId, out userToken) || userToken == IntPtr.Zero)
                return (false, $"could not obtain the session's user token (error {Marshal.GetLastWin32Error()})");

            if (!DuplicateTokenEx(userToken, MaximumAllowed, IntPtr.Zero,
                                  SecurityImpersonation, TokenPrimary, out primaryToken))
                return (false, $"could not duplicate the session token (error {Marshal.GetLastWin32Error()})");

            // Not fatal on its own: a process with a null environment block still starts, it
            // just inherits none of the user's variables. For rundll32 that is fine.
            CreateEnvironmentBlock(out environment, primaryToken, false);

            var startup = new STARTUPINFO
            {
                cb = Marshal.SizeOf<STARTUPINFO>(),
                lpDesktop = @"winsta0\default",
            };

            // A single command line, quoted, because CreateProcessAsUser takes one string and
            // parses it itself. The values are ASTRA's own constants — see the class note.
            var commandLine = $"\"{Environment.SystemDirectory}\\{exeName}\" {arguments}";

            var created = CreateProcessAsUser(
                primaryToken,
                null,
                commandLine,
                IntPtr.Zero, IntPtr.Zero,
                false,
                CreateUnicodeEnvironment | CreateNoWindow,
                environment,
                null,
                ref startup,
                out var processInfo);

            if (!created)
                return (false, $"could not start {exeName} in session {sessionId} (error {Marshal.GetLastWin32Error()})");

            // Nothing waits on the process — the point is that it runs in the user's session,
            // not that it finishes before this method returns — but the handles are ours and
            // leaking one per lock would be a handle leak in a service that runs for months.
            if (processInfo.hProcess != IntPtr.Zero) CloseHandle(processInfo.hProcess);
            if (processInfo.hThread != IntPtr.Zero) CloseHandle(processInfo.hThread);
            return (true, "started");
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
        finally
        {
            if (environment != IntPtr.Zero) DestroyEnvironmentBlock(environment);
            if (primaryToken != IntPtr.Zero) CloseHandle(primaryToken);
            if (userToken != IntPtr.Zero) CloseHandle(userToken);
        }
    }

    private const int MaximumAllowed = 0x2000000;
    private const int SecurityImpersonation = 2;
    private const int TokenPrimary = 1;
    private const uint CreateUnicodeEnvironment = 0x00000400;
    private const uint CreateNoWindow = 0x08000000;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct STARTUPINFO
    {
        public int cb;
        public string? lpReserved;
        public string? lpDesktop;
        public string? lpTitle;
        public int dwX, dwY, dwXSize, dwYSize;
        public int dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow, cbReserved2;
        public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PROCESS_INFORMATION
    {
        public IntPtr hProcess, hThread;
        public int dwProcessId, dwThreadId;
    }

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool DuplicateTokenEx(
        IntPtr existingToken, int desiredAccess, IntPtr tokenAttributes,
        int impersonationLevel, int tokenType, out IntPtr newToken);

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CreateProcessAsUser(
        IntPtr token, string? applicationName, string? commandLine,
        IntPtr processAttributes, IntPtr threadAttributes, bool inheritHandles,
        uint creationFlags, IntPtr environment, string? currentDirectory,
        ref STARTUPINFO startupInfo, out PROCESS_INFORMATION processInformation);

    [DllImport("userenv.dll", SetLastError = true)]
    private static extern bool CreateEnvironmentBlock(
        out IntPtr environment, IntPtr token, bool inherit);

    [DllImport("userenv.dll", SetLastError = true)]
    private static extern bool DestroyEnvironmentBlock(IntPtr environment);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);
}
