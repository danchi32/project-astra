using System.Security.Cryptography;
using System.Text;

namespace AstraAgent.Service.Security;

public interface ITokenStore
{
    void Save(string token);
    string? Load();
    void Clear();
}

/// <summary>Persists the device credential encrypted with DPAPI (LocalMachine scope,
/// readable only on this machine) — never plaintext on disk.</summary>
public sealed class DpapiTokenStore : ITokenStore
{
    private readonly string _path;

    public DpapiTokenStore()
        : this(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "Astra", "agent.credential"))
    {
    }

    public DpapiTokenStore(string path) => _path = path;

    public void Save(string token)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        var protectedBytes = ProtectedData.Protect(
            Encoding.UTF8.GetBytes(token), optionalEntropy: null, DataProtectionScope.LocalMachine);
        File.WriteAllBytes(_path, protectedBytes);
    }

    public string? Load()
    {
        if (!File.Exists(_path))
            return null;
        try
        {
            var bytes = ProtectedData.Unprotect(
                File.ReadAllBytes(_path), optionalEntropy: null, DataProtectionScope.LocalMachine);
            return Encoding.UTF8.GetString(bytes);
        }
        catch (CryptographicException)
        {
            // Corrupted or copied from another machine — treat as not enrolled.
            return null;
        }
    }

    public void Clear()
    {
        if (File.Exists(_path))
            File.Delete(_path);
    }
}
