using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Win32;

namespace AstraAgent.Service.Guard;

public enum HostChange { None, Registered, Unregistered }

/// <summary>
/// Phase 3 · D3: tells each browser where SAVIO's native messaging host
/// (<c>savio-guard-host.exe</c>, shipped beside the service) is, and which extension may start it.
///
/// A browser finds a host by name under <c>HKLM\SOFTWARE\&lt;vendor&gt;\NativeMessagingHosts</c>;
/// the key's default value is the path of a JSON manifest naming the exe and the one extension
/// allowed to use it. The manifests sit in the install folder, beside the exe, where only
/// administrators can write. A manifest in a user-writable folder would let any user point
/// another user's browser at a program of their choosing.
///
/// Registered only while the org's policy forces the extension in, and removed when it no
/// longer does. The name com.savio.guard is SAVIO's own, so it is simply written, never
/// treated as someone else's setting.
/// </summary>
public static class NativeHostRegistration
{
    public const string HostName = "com.savio.guard";
    public const string HostExe = "savio-guard-host.exe";

    public static string RegistryPath(Browser b) => b switch
    {
        Browser.Chrome => $@"SOFTWARE\Google\Chrome\NativeMessagingHosts\{HostName}",
        Browser.Edge => $@"SOFTWARE\Microsoft\Edge\NativeMessagingHosts\{HostName}",
        Browser.Firefox => $@"SOFTWARE\Mozilla\NativeMessagingHosts\{HostName}",
        _ => throw new ArgumentOutOfRangeException(nameof(b)),
    };

    /// <summary>Registers the host for one browser's extension, or with a null
    /// <paramref name="extensionId"/> removes the registration. Idempotent.</summary>
    public static HostChange Apply(RegistryKey root, Browser b, string? extensionId, string hostExePath, string manifestDir)
    {
        var key = RegistryPath(b);
        var manifestPath = Path.Combine(manifestDir, $"{HostName}.{b.ToString().ToLowerInvariant()}.json");

        if (extensionId is null)
        {
            bool had;
            using (var k = root.OpenSubKey(key)) had = k is not null;
            if (had) root.DeleteSubKeyTree(key, false);
            if (File.Exists(manifestPath)) { File.Delete(manifestPath); had = true; }
            return had ? HostChange.Unregistered : HostChange.None;
        }

        var manifest = new JsonObject
        {
            ["name"] = HostName,
            ["description"] = "SAVIO AI Guard: checks text for sensitive data on this PC, answers with counts only",
            ["path"] = hostExePath,
            ["type"] = "stdio",
            // Firefox names extensions by ID; Chrome and Edge by origin.
            [b == Browser.Firefox ? "allowed_extensions" : "allowed_origins"] =
                new JsonArray(b == Browser.Firefox ? extensionId : $"chrome-extension://{extensionId}/"),
        }.ToJsonString(new JsonSerializerOptions { WriteIndented = true });

        var changed = false;
        if (!File.Exists(manifestPath) || File.ReadAllText(manifestPath) != manifest)
        {
            Directory.CreateDirectory(manifestDir);
            File.WriteAllText(manifestPath, manifest);
            changed = true;
        }
        using (var k = root.CreateSubKey(key, writable: true))
            if (k.GetValue("") as string != manifestPath) { k.SetValue("", manifestPath, RegistryValueKind.String); changed = true; }
        return changed ? HostChange.Registered : HostChange.None;
    }
}
