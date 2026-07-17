using System.Security.Cryptography;
using System.Text;
using AstraAgent.Service.Update;
using Xunit;

namespace AstraAgent.Service.Tests;

public class UpdateVerifierTests
{
    // A throwaway keypair generated per test run — the "release signing" side.
    private static (UpdateVerifier Verifier, RSA Signer) NewPair()
    {
        var signer = RSA.Create(3072);
        var pubPem = signer.ExportSubjectPublicKeyInfoPem();
        var verifier = UpdateVerifier.FromPublicKeyPem(pubPem);
        Assert.NotNull(verifier);
        return (verifier!, signer);
    }

    private static string Sign(RSA signer, string manifestJson)
    {
        var sig = signer.SignData(
            Encoding.UTF8.GetBytes(manifestJson), HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
        return Convert.ToBase64String(sig);
    }

    private const string SampleManifest =
        "{\"version\":\"0.2.0\",\"url\":\"https://example.com/a.zip\",\"sha256\":\"ABCD\"}";

    [Fact]
    public void ValidlySignedManifest_Verifies()
    {
        var (verifier, signer) = NewPair();
        var manifest = verifier.Verify(SampleManifest, Sign(signer, SampleManifest));
        Assert.NotNull(manifest);
        Assert.Equal("0.2.0", manifest!.Version);
        Assert.Equal("https://example.com/a.zip", manifest.Url);
    }

    [Fact]
    public void TamperedManifest_IsRejected()
    {
        var (verifier, signer) = NewPair();
        var signature = Sign(signer, SampleManifest);
        // Change the URL after signing — signature no longer covers these bytes.
        var tampered = SampleManifest.Replace("example.com", "evil.com");
        Assert.Null(verifier.Verify(tampered, signature));
    }

    [Fact]
    public void SignatureFromADifferentKey_IsRejected()
    {
        var (verifier, _) = NewPair();
        using var attacker = RSA.Create(3072);   // not the pinned key
        Assert.Null(verifier.Verify(SampleManifest, Sign(attacker, SampleManifest)));
    }

    [Fact]
    public void GarbageSignature_IsRejected()
    {
        var (verifier, _) = NewPair();
        Assert.Null(verifier.Verify(SampleManifest, "not-base64!!"));
        Assert.Null(verifier.Verify(SampleManifest, Convert.ToBase64String(new byte[] { 1, 2, 3 })));
    }

    [Fact]
    public void PlaceholderKey_YieldsNoVerifier_SoUpdatesStayOff()
    {
        // The shipped placeholder is not a key; the embedded loader must refuse it (fail-safe).
        Assert.Null(UpdateVerifier.FromPublicKeyPem("PLACEHOLDER — not a key"));
        Assert.Null(UpdateVerifier.FromPublicKeyPem(null));
        Assert.Null(UpdateVerifier.FromPublicKeyPem(""));
    }

    [Fact]
    public void UndersizedKey_IsRefused()
    {
        using var weak = RSA.Create(1024);
        Assert.Null(UpdateVerifier.FromPublicKeyPem(weak.ExportSubjectPublicKeyInfoPem()));
    }

    [Fact]
    public void FileMatchesHash_DetectsTamper()
    {
        var path = Path.GetTempFileName();
        try
        {
            File.WriteAllText(path, "hello world");
            var good = Convert.ToHexString(
                SHA256.HashData(Encoding.UTF8.GetBytes("hello world")));
            Assert.True(UpdateVerifier.FileMatchesHash(path, good));
            Assert.True(UpdateVerifier.FileMatchesHash(path, good.ToLowerInvariant()));
            Assert.False(UpdateVerifier.FileMatchesHash(path, new string('0', 64)));
        }
        finally
        {
            File.Delete(path);
        }
    }
}

public class SemVerTests
{
    [Theory]
    [InlineData("0.2.0", "0.1.0", true)]
    [InlineData("1.0.0", "0.9.9", true)]
    [InlineData("0.1.1", "0.1.0", true)]
    [InlineData("0.1.0", "0.1.0", false)]   // equal is not newer
    [InlineData("0.1.0", "0.2.0", false)]   // older
    [InlineData("v0.2.0", "0.1.0", true)]   // tolerant of a leading v
    [InlineData("garbage", "0.1.0", false)] // unparseable never looks newer
    public void IsNewer_Works(string candidate, string current, bool expected)
        => Assert.Equal(expected, SemVer.IsNewer(candidate, current));
}
