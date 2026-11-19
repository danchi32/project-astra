using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace AstraAgent.GuardHost;

/// <summary>
/// Security review (3b) H1: the USB scan runs as LocalSystem on paths a standard user controls.
/// A link planted on the drive (a junction to <c>\RPC Control</c> with an object-manager link to
/// <c>\??\UNC\attacker\share</c>) would make SYSTEM open a file on an attacker's server and send
/// the PC's own NTLM login with it, or read another user's files.
///
/// Three layers, each enough on its own most of the time:
/// <list type="number">
/// <item>Redirection Guard: the process follows only junctions an administrator made
/// (<c>ProcessRedirectionTrustPolicy</c>, Windows 11 22H2 and later; best effort elsewhere).</item>
/// <item>No link anywhere on the way: every folder below the drive root, and the file, is
/// checked for a reparse point before the file is opened.</item>
/// <item>After opening, the file's final path must still be on that drive; the bytes are read
/// from that same handle, so nothing can be swapped in between.</item>
/// </list>
/// ponytail: without Redirection Guard (older Windows) a link swapped in between check 2 and the
/// open can still reach the server once, though nothing is read from it. Upgrade path: run the
/// scan under the console user's token (a launcher with redirected output), so a leaked login is
/// only the user's own.
/// </summary>
internal static class SafeOpen
{
    /// <summary>Best effort; false where Windows does not have it.</summary>
    public static bool TrustOnlyAdminRedirections()
    {
        var policy = new RedirectionTrust { Flags = 1 };   // EnforceRedirectionTrust
        return SetProcessMitigationPolicy(ProcessRedirectionTrustPolicy, ref policy, Marshal.SizeOf<RedirectionTrust>());
    }

    /// <summary>The file's bytes when nothing on the way to it is a link and it is really on
    /// <paramref name="root"/>'s drive, else null.</summary>
    public static byte[]? ReadUnder(string root, string path, long maxBytes)
    {
        var full = Path.GetFullPath(path);
        root = Path.GetFullPath(root);
        if (!root.EndsWith('\\')) root += '\\';
        if (!full.StartsWith(root, StringComparison.OrdinalIgnoreCase) || full.Length == root.Length) return null;
        for (var p = full; p.Length > root.Length; p = Path.GetDirectoryName(p)!)
            if (File.GetAttributes(p).HasFlag(FileAttributes.ReparsePoint)) return null;

        using var handle = File.OpenHandle(full, FileMode.Open, FileAccess.Read, FileShare.Read);
        var final = FinalPath(handle);
        if (final is null || !final.StartsWith(@"\\?\" + root, StringComparison.OrdinalIgnoreCase)) return null;
        var length = RandomAccess.GetLength(handle);
        if (length > maxBytes) return null;
        var bytes = new byte[length];
        var read = 0;
        while (read < length)
        {
            var n = RandomAccess.Read(handle, bytes.AsSpan(read), read);
            if (n == 0) break;
            read += n;
        }
        return read == length ? bytes : bytes[..read];
    }

    static string? FinalPath(SafeFileHandle handle)
    {
        var sb = new StringBuilder(1024);
        var n = GetFinalPathNameByHandle(handle, sb, (uint)sb.Capacity, 0);
        return n == 0 || n >= sb.Capacity ? null : sb.ToString();
    }

    const int ProcessRedirectionTrustPolicy = 16;

    [StructLayout(LayoutKind.Sequential)]
    struct RedirectionTrust { public uint Flags; }

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetProcessMitigationPolicy(int policy, ref RedirectionTrust buffer, int length);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode, EntryPoint = "GetFinalPathNameByHandleW")]
    static extern uint GetFinalPathNameByHandle(SafeFileHandle handle, StringBuilder path, uint length, uint flags);
}
