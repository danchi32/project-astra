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

    private const string Sha64 =
        "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789";

    private const string SampleManifest =
        "{\"version\":\"0.2.0\",\"url\":\"https://example.com/a.zip\",\"sha256\":\"" + Sha64 + "\"}";

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
    public void EmbeddedKey_IsPinned_SoAutoUpdateIsArmed()
    {
        // Once a real public key is pinned into update-signing-public.pem, the embedded loader
        // must produce a verifier (auto-update armed). If this fails, the placeholder is still
        // in place or the pasted key is malformed.
        Assert.NotNull(UpdateVerifier.FromEmbeddedKey());
    }

    [Fact]
    public void UndersizedKey_IsRefused()
    {
        using var weak = RSA.Create(1024);
        Assert.Null(UpdateVerifier.FromPublicKeyPem(weak.ExportSubjectPublicKeyInfoPem()));
    }

    [Theory]
    // Even with a VALID signature, a malformed field must be refused (defense in depth).
    [InlineData("{\"version\":\"..\\\\evil\",\"url\":\"https://x/a.zip\",\"sha256\":\"" + Sha64 + "\"}")]
    [InlineData("{\"version\":\"0.2\",\"url\":\"https://x/a.zip\",\"sha256\":\"" + Sha64 + "\"}")]
    [InlineData("{\"version\":\"0.2.0\",\"url\":\"https://x/a.zip\",\"sha256\":\"tooshort\"}")]
    [InlineData("{\"version\":\"0.2.0\",\"url\":\"http://x/a.zip\",\"sha256\":\"" + Sha64 + "\"}")]
    [InlineData("{\"version\":\"0.2.0\",\"url\":\"file:///etc/passwd\",\"sha256\":\"" + Sha64 + "\"}")]
    public void MalformedButSignedManifest_IsRejected(string json)
    {
        var (verifier, signer) = NewPair();
        Assert.Null(verifier.Verify(json, Sign(signer, json)));
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

public class UpdateFloorStoreTests
{
    [Fact]
    public void Raise_IsMonotonic_AndPersists()
    {
        var path = Path.Combine(Path.GetTempPath(), $"floor-{Guid.NewGuid():N}.txt");
        try
        {
            var store = new UpdateFloorStore(path);
            Assert.Equal("0.0.0", store.Current());

            store.Raise("0.3.0");
            Assert.Equal("0.3.0", store.Current());

            store.Raise("0.2.0");                 // older — must not lower the floor
            Assert.Equal("0.3.0", store.Current());

            store.Raise("0.4.0");
            Assert.Equal("0.4.0", store.Current());

            // A fresh store over the same file sees the persisted floor (survives restart).
            Assert.Equal("0.4.0", new UpdateFloorStore(path).Current());
        }
        finally
        {
            if (File.Exists(path)) File.Delete(path);
        }
    }
}

public class UpdateApplicabilityTests
{
    [Theory]
    // The regression: a fresh device (floor 0.0.0) running 0.5.1 MUST accept an offered 0.6.0.
    // The old code raised the floor to the offered version first, so it refused its own update.
    [InlineData("0.5.1", "0.6.0", "0.0.0", true)]
    [InlineData("0.5.1", "0.6.0", "0.5.1", true)]   // floor already at the running version
    [InlineData("0.6.0", "0.6.0", "0.0.0", false)]  // already on the offered version
    [InlineData("0.5.1", "0.5.0", "0.0.0", false)]  // an older manifest is refused
    [InlineData("0.5.1", "0.6.0", "0.7.0", false)]  // floor above the offer (replay/rollback) refused
    // A floor EQUAL to the offered version is a permanent deadlock: strictly-newer can never be
    // satisfied, so the device sticks on `current` until a higher version ships. This is exactly
    // the state a failed apply used to leave behind, and the reason the floor is now only ever
    // raised to a version the agent has actually run.
    [InlineData("0.8.4", "0.8.5", "0.8.5", false)]
    public void IsApplicable_AcceptsNewer_RefusesReplays(
        string current, string manifestVersion, string floor, bool expected)
        => Assert.Equal(expected, UpdatePolicy.IsApplicable(
            current, manifestVersion, floor));

    /// <summary>The regression that stranded a device on 0.8.4: an offered version must stay
    /// applicable across *repeated failed applies*. Raising the floor only to the running version
    /// (what UpdateWorker does now) keeps the offer alive; raising it to the offered version — the
    /// old behaviour, reproduced here — locks the device out of that release permanently.</summary>
    [Fact]
    public void FailedApply_DoesNotStrandTheDeviceOnTheOldVersion()
    {
        var path = Path.Combine(Path.GetTempPath(), $"floor-{Guid.NewGuid():N}.txt");
        try
        {
            const string running = "0.8.4";
            const string offered = "0.8.5";
            var floor = new UpdateFloorStore(path);

            // Startup records what actually runs, then an apply is attempted and fails. Three
            // times over, the update must still be on the table.
            for (var attempt = 0; attempt < 3; attempt++)
            {
                floor.Raise(running);
                Assert.True(
                    UpdatePolicy.IsApplicable(running, offered, floor.Current()),
                    $"attempt {attempt}: 0.8.5 must stay applicable after a failed apply");
            }

            // The rollback protection the floor exists for is still intact.
            Assert.Equal(running, floor.Current());
            Assert.False(
                UpdatePolicy.IsApplicable(running, "0.8.3", floor.Current()),
                "a replayed older manifest must still be refused");

            // Contrast: recording the mere OFFER is what deadlocks it.
            floor.Raise(offered);
            Assert.False(
                UpdatePolicy.IsApplicable(running, offered, floor.Current()),
                "floor == offered version is unrecoverable — never write it for an un-run version");
        }
        finally
        {
            if (File.Exists(path)) File.Delete(path);
        }
    }

    /// <summary>A mandatory release names itself as the floor (`min_version == version`). Honouring
    /// that literally would put the floor at the offered version and make the mandatory update
    /// itself uninstallable, so only a min_version strictly below the offer may be persisted.</summary>
    [Theory]
    [InlineData("0.9.0", "0.9.0", false)]   // mandatory release — must NOT be persisted
    [InlineData("0.9.0", "0.8.9", true)]    // revokes older builds — safe to persist
    [InlineData("0.9.0", "0.9.1", false)]   // self-inconsistent (floor above its own offer)
    public void MinVersion_IsPersistedOnlyWhenBelowTheOffer(
        string offered, string minVersion, bool shouldPersist)
    {
        var persists = UpdatePolicy.ShouldPersistMinVersion(offered, minVersion);
        Assert.Equal(shouldPersist, persists);

        // Whatever the manifest claims, the offer itself must survive the decision.
        var floor = persists ? minVersion : "0.0.0";
        Assert.True(
            UpdatePolicy.IsApplicable("0.8.6", offered, floor),
            "a mandatory release must remain installable");
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

public class UpdatePolicySharingTests
{
    /// <summary>The tray updater used to carry its own copy of this arithmetic, and its copy
    /// raised the floor to the offered version before comparing against it — which made the
    /// comparison unsatisfiable, so the tray never self-updated on any device. Both updaters now
    /// go through UpdatePolicy; this pins the shape that broke.</summary>
    [Fact]
    public void RaisingTheFloorToTheOffer_MakesEveryUpdateImpossible()
    {
        var path = Path.Combine(Path.GetTempPath(), $"floor-{Guid.NewGuid():N}.txt");
        try
        {
            var floor = new UpdateFloorStore(path);

            // The old tray sequence: raise to the offer, THEN ask if the offer is applicable.
            foreach (var offered in new[] { "0.8.5", "0.8.6", "1.0.0" })
            {
                floor.Raise(offered);
                Assert.False(
                    UpdatePolicy.IsApplicable("0.8.4", offered, floor.Current()),
                    $"{offered}: raising the floor to the offer can never be applicable");
            }

            // The corrected sequence: the floor only tracks what is running, so the offer stands.
            var good = new UpdateFloorStore(
                Path.Combine(Path.GetTempPath(), $"floor-{Guid.NewGuid():N}.txt"));
            good.Raise("0.8.4");
            Assert.True(UpdatePolicy.IsApplicable("0.8.4", "0.8.5", good.Current()));
        }
        finally
        {
            if (File.Exists(path)) File.Delete(path);
        }
    }
}
