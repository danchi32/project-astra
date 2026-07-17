using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace AstraAgent.Service.Update;

/// <summary>
/// Verifies agent update manifests against a public key that is PINNED into this binary.
///
/// This is the security boundary for auto-update. The matching private key never touches the
/// backend — releases are signed in CI with an offline/CI-held key, and the backend only
/// relays the already-signed manifest. So even a full backend compromise cannot forge an
/// update: an attacker would still need the private signing key to produce a valid signature,
/// and this agent rejects anything that doesn't verify.
///
/// The verifier is INERT until a real public key is embedded (see update-signing-public.pem).
/// With the placeholder in place, <see cref="FromEmbeddedKey"/> returns null and the agent
/// simply never auto-updates — fail-safe, never fail-open.
/// </summary>
public sealed class UpdateVerifier
{
    private const string EmbeddedKeyResource =
        "AstraAgent.Service.Update.update-signing-public.pem";

    // Strict shapes for the fields that flow into file paths and the apply script. Even though
    // these are signature-gated, validating them is cheap defense-in-depth against a version
    // like "..\..\evil" or a quote-breakout ever reaching Path.Combine / the .cmd.
    private static readonly Regex VersionRe = new(@"^\d+\.\d+\.\d+$", RegexOptions.Compiled);
    private static readonly Regex Sha256Re = new(@"^[0-9a-fA-F]{64}$", RegexOptions.Compiled);

    private readonly RSA _publicKey;

    private UpdateVerifier(RSA publicKey) => _publicKey = publicKey;

    /// <summary>Build a verifier from the given PEM public key, or null if it isn't a usable key.</summary>
    public static UpdateVerifier? FromPublicKeyPem(string? pem)
    {
        if (string.IsNullOrWhiteSpace(pem) || !pem.Contains("BEGIN PUBLIC KEY"))
            return null;
        try
        {
            var rsa = RSA.Create();
            rsa.ImportFromPem(pem);
            // Reject an undersized key even if it parses — 2048-bit minimum.
            if (rsa.KeySize < 2048)
            {
                rsa.Dispose();
                return null;
            }
            return new UpdateVerifier(rsa);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>Load the verifier from the public key pinned into this assembly, or null when the
    /// placeholder key is still in place (auto-update stays disabled).</summary>
    public static UpdateVerifier? FromEmbeddedKey()
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(EmbeddedKeyResource);
        if (stream is null)
            return null;
        using var reader = new StreamReader(stream);
        return FromPublicKeyPem(reader.ReadToEnd());
    }

    /// <summary>Verify the signature over the EXACT manifest bytes, then parse it. Returns null if
    /// the signature is invalid or the manifest is malformed — callers must treat null as "do not
    /// update". The manifest string is verified verbatim; it is never re-serialized first.</summary>
    public UpdateManifest? Verify(string manifestJson, string signatureBase64)
    {
        if (string.IsNullOrEmpty(manifestJson) || string.IsNullOrEmpty(signatureBase64))
            return null;

        byte[] signature;
        try
        {
            signature = Convert.FromBase64String(signatureBase64);
        }
        catch (FormatException)
        {
            return null;
        }

        var data = Encoding.UTF8.GetBytes(manifestJson);
        bool ok;
        try
        {
            ok = _publicKey.VerifyData(
                data, signature, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
        }
        catch (CryptographicException)
        {
            return null;
        }
        if (!ok)
            return null;

        try
        {
            var manifest = JsonSerializer.Deserialize<UpdateManifest>(manifestJson);
            if (manifest is null || !IsWellFormed(manifest))
                return null;
            return manifest;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    /// <summary>Reject a manifest whose fields aren't strictly shaped, so nothing unexpected can
    /// reach a file path or the generated apply script even behind a valid signature.</summary>
    private static bool IsWellFormed(UpdateManifest m)
    {
        if (!VersionRe.IsMatch(m.Version ?? ""))
            return false;
        if (!Sha256Re.IsMatch(m.Sha256 ?? ""))
            return false;
        if (!Uri.TryCreate(m.Url, UriKind.Absolute, out var uri) || uri.Scheme != Uri.UriSchemeHttps)
            return false;
        if (m.MinVersion is not null && !VersionRe.IsMatch(m.MinVersion))
            return false;
        return true;
    }

    /// <summary>Confirm a downloaded file's SHA-256 matches the (already signature-verified)
    /// manifest, so a tampered or truncated download is rejected before it's ever executed.</summary>
    public static bool FileMatchesHash(string filePath, string expectedSha256Hex)
    {
        using var stream = File.OpenRead(filePath);
        var actual = Convert.ToHexString(SHA256.HashData(stream));
        return actual.Equals(expectedSha256Hex.Trim(), StringComparison.OrdinalIgnoreCase);
    }
}
