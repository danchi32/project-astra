using System.Security.AccessControl;
using System.Security.Principal;

namespace AstraAgent.Service.Update;

/// <summary>Locates and locks down the update working area.
///
/// This must NOT live under a world-writable root like C:\ProgramData: the LocalSystem
/// service writes an apply script there and executes it, so if an unprivileged user could
/// pre-create or tamper with that directory they'd gain SYSTEM code execution. We put it under
/// the admin-only install root (Program Files\Astra) AND stamp an explicit SYSTEM/Administrators
/// -only DACL, refusing to proceed if we can't secure it (fail-safe).</summary>
internal static class UpdatePaths
{
    /// <summary>`...\Astra\update`, a sibling of the service's install dir (`...\Astra\Agent`).
    /// Under Program Files this is not user-writable by default; the DACL below enforces it
    /// regardless of where the agent happens to be installed.</summary>
    public static string WorkRoot { get; } = Path.Combine(
        Path.GetDirectoryName(AppContext.BaseDirectory.TrimEnd('\\')) ?? AppContext.BaseDirectory,
        "update");

    /// <summary>Create (or re-secure) WorkRoot so only SYSTEM and Administrators can touch it.
    /// Throws if the directory can't be locked down — callers treat that as "do not update".</summary>
    public static void EnsureHardened() => Security.SecureDirectory.Ensure(WorkRoot);
}
