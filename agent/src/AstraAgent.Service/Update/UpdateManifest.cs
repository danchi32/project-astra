using System.Text.Json.Serialization;

namespace AstraAgent.Service.Update;

/// <summary>The signed description of an available agent release. The backend serves the
/// exact bytes that were signed at release time; the agent verifies the signature against a
/// pinned public key before trusting a single field of it.</summary>
public sealed record UpdateManifest(
    [property: JsonPropertyName("version")] string Version,
    [property: JsonPropertyName("url")] string Url,
    [property: JsonPropertyName("sha256")] string Sha256,
    [property: JsonPropertyName("notes")] string? Notes = null,
    // Optional signed hard floor: agents refuse to run any version below this and remember the
    // highest floor they've ever seen, so a released fix can revoke known-bad earlier versions.
    [property: JsonPropertyName("min_version")] string? MinVersion = null);

/// <summary>What the backend returns from GET /api/v1/agent/update. `Manifest` is the raw JSON
/// string that was signed (verified verbatim — never re-serialized), `Signature` its base64
/// RSA-SHA256 signature. `Available` is false when the org has no update channel configured.</summary>
public sealed record UpdateEnvelope(
    [property: JsonPropertyName("available")] bool Available,
    [property: JsonPropertyName("manifest")] string? Manifest,
    [property: JsonPropertyName("signature")] string? Signature);
