using System.IO;
using System.Security.AccessControl;
using System.Security.Principal;

namespace AstraAgent.Service.Security;

/// <summary>A folder only SYSTEM and Administrators can touch, for anything the LocalSystem
/// service writes, reads back or deletes.
///
/// Why it matters: a folder a standard user can create or own (anything under C:\ProgramData
/// gets "Users: create" by inheritance) lets that user plant a junction, so SYSTEM's next write
/// or delete lands wherever they point it — a known route to SYSTEM. And a file Users can read
/// (the device credential is LocalMachine-DPAPI, which any local account can decrypt) is a
/// file every user on the PC can steal.
///
/// Fails closed: callers treat an exception as "don't use this folder".</summary>
public static class SecureDirectory
{
    private static readonly SecurityIdentifier SystemSid = new(WellKnownSidType.LocalSystemSid, null);
    private static readonly SecurityIdentifier AdminsSid = new(WellKnownSidType.BuiltinAdministratorsSid, null);

    public static void Ensure(string path)
    {
        var security = new DirectorySecurity();
        // Break inheritance and drop any inherited Users / CREATOR OWNER rights.
        security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);
        foreach (var sid in new[] { SystemSid, AdminsSid })
        {
            security.AddAccessRule(new FileSystemAccessRule(
                sid, FileSystemRights.FullControl,
                InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                PropagationFlags.None, AccessControlType.Allow));
        }
        try { security.SetOwner(AdminsSid); } catch { /* needs privilege; the DACL is the guard */ }

        var info = new DirectoryInfo(path);
        if (!info.Exists)
        {
            FileSystemAclExtensions.CreateDirectory(security, path);
            return;
        }
        // A junction here is exactly the planted redirect this class exists to stop.
        if (info.Attributes.HasFlag(FileAttributes.ReparsePoint))
            throw new IOException($"Refusing to use '{path}': it is a junction or link.");
        // A pre-existing folder may carry a weak DACL (planted, or from an older agent).
        info.SetAccessControl(security);
    }

    /// <summary>Lock one existing file down the same way — a file created before its folder was
    /// hardened keeps the explicit ACL it was born with.</summary>
    public static void EnsureFile(string path)
    {
        var info = new FileInfo(path);
        if (!info.Exists) return;
        if (info.Attributes.HasFlag(FileAttributes.ReparsePoint))
            throw new IOException($"Refusing to use '{path}': it is a link.");
        var security = new FileSecurity();
        security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);
        foreach (var sid in new[] { SystemSid, AdminsSid })
            security.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl, AccessControlType.Allow));
        try { security.SetOwner(AdminsSid); } catch { /* as above */ }
        info.SetAccessControl(security);
    }

    /// <summary>`...\Astra\state`, a sibling of the service's install dir — under Program Files,
    /// so no standard user can pre-create it before the service does.</summary>
    public static string StateRoot { get; } = Path.Combine(
        Path.GetDirectoryName(System.AppContext.BaseDirectory.TrimEnd('\\')) ?? System.AppContext.BaseDirectory,
        "state");
}
