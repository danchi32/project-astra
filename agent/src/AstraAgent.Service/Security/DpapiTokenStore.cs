using System.Security.Cryptography;
using System.Text;

namespace AstraAgent.Service.Security;

public interface ITokenStore
{
    void Save(string token);
    string? Load();
    void Clear();
}

/// <summary>Persists the device credential encrypted with DPAPI (LocalMachine scope: only
/// this machine can decrypt it) in a file only SYSTEM and Administrators can read.</summary>
public sealed class DpapiTokenStore : ITokenStore
{
    private readonly string _path;
    private readonly bool _harden;

    // LocalMachine DPAPI can be decrypted by ANY account on this PC, so the file's ACL is what
    // keeps the device token from every signed-in user. ProgramData\Astra used to inherit
    // "Users: read" — the folder and the file are locked to SYSTEM + Administrators on every
    // save and load, which also repairs devices enrolled by an older agent.
    public DpapiTokenStore()
        : this(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "Astra", "agent.credential"))
    {
        _harden = true;
    }

    public DpapiTokenStore(string path) => _path = path;

    private void Harden(bool strict)
    {
        if (!_harden) return;
        try
        {
            SecureDirectory.Ensure(Path.GetDirectoryName(_path)!);
            SecureDirectory.EnsureFile(_path);
        }
        // A junction in place of the folder is an attack: never write the token through it.
        catch (IOException) when (strict) { throw; }
        catch (Exception) { /* best effort on read; the next save tries again */ }
    }

    public void Save(string token)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        Harden(strict: true);
        var protectedBytes = ProtectedData.Protect(
            Encoding.UTF8.GetBytes(token), optionalEntropy: null, DataProtectionScope.LocalMachine);
        File.WriteAllBytes(_path, protectedBytes);
        Harden(strict: true);
    }

    public string? Load()
    {
        if (!File.Exists(_path))
            return null;
        Harden(strict: false);
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
