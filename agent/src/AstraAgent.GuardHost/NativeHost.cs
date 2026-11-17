using System.Buffers.Binary;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using AstraAgent.Guard;

namespace AstraAgent.GuardHost;

/// <summary>
/// Phase 3 · D3: the browser's native messaging protocol, and the one thing this host does.
///
/// Each message is a 4-byte little-endian length followed by that many bytes of UTF-8 JSON, in
/// both directions (Chrome, Edge and Firefox all use this framing). A request is
/// <c>{"type":"scan","text":"…","keywords":[…]}</c>. The answer is counts and flags only:
/// what kind of thing was found and how much, never the text. The host keeps nothing. It
/// writes nothing to disk and nothing to a log, so text pasted into a browser exists only in
/// this process's memory for the length of one scan.
/// </summary>
public static class NativeHost
{
    /// <summary>Chrome's limit for a message *to* the host is 64 MiB. Ours is far lower: the
    /// scanner caps at 5M characters anyway, and a larger frame is refused before it is read.</summary>
    public const int MaxRequestBytes = 16 * 1024 * 1024;

    static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public sealed record Request(string? Type, string? Text, IReadOnlyList<string>? Keywords);

    public sealed record Response(
        bool Ok,
        string? Error = null,
        IReadOnlyDictionary<string, int>? Counts = null,
        bool ContactList = false,
        IReadOnlyList<int>? KeywordHits = null,
        bool Truncated = false,
        bool Incomplete = false);

    /// <summary>Serve one connection until the browser closes stdin.</summary>
    public static async Task RunAsync(Stream input, Stream output, CancellationToken ct = default)
    {
        while (!ct.IsCancellationRequested)
        {
            var frame = await ReadFrameAsync(input, ct);
            if (frame is null)
                return;                                   // the browser disconnected
            await WriteFrameAsync(output, Handle(frame), ct);
        }
    }

    public static Response Handle(byte[] frame)
    {
        Request? req;
        try { req = JsonSerializer.Deserialize<Request>(frame, Json); }
        catch (JsonException) { return new Response(false, "malformed request"); }
        if (req?.Type != "scan")
            return new Response(false, "unknown request");

        var r = PiiScanner.Scan(req.Text, req.Keywords);
        return new Response(
            Ok: true,
            Counts: r.Counts.Where(kv => kv.Value > 0).ToDictionary(kv => kv.Key.ToString(), kv => kv.Value),
            ContactList: r.ContactList,
            KeywordHits: r.KeywordHits,
            Truncated: r.Truncated,
            Incomplete: r.Incomplete);
    }

    /// <summary>Null at end of stream. A frame over the limit throws: the connection is not
    /// worth keeping, and the browser starts a new host for the next one.</summary>
    public static async Task<byte[]?> ReadFrameAsync(Stream input, CancellationToken ct)
    {
        var header = new byte[4];
        if (!await ReadExactlyOrEndAsync(input, header, ct))
            return null;
        var length = BinaryPrimitives.ReadInt32LittleEndian(header);
        if (length < 0 || length > MaxRequestBytes)
            throw new InvalidDataException($"message of {length} bytes refused");
        var body = new byte[length];
        if (!await ReadExactlyOrEndAsync(input, body, ct))
            throw new EndOfStreamException("message cut short");
        return body;
    }

    public static async Task WriteFrameAsync(Stream output, Response response, CancellationToken ct)
    {
        var body = JsonSerializer.SerializeToUtf8Bytes(response, Json);
        var header = new byte[4];
        BinaryPrimitives.WriteInt32LittleEndian(header, body.Length);
        await output.WriteAsync(header, ct);
        await output.WriteAsync(body, ct);
        await output.FlushAsync(ct);
    }

    static async Task<bool> ReadExactlyOrEndAsync(Stream s, byte[] buffer, CancellationToken ct)
    {
        int read = 0;
        while (read < buffer.Length)
        {
            int n = await s.ReadAsync(buffer.AsMemory(read), ct);
            if (n == 0)
                return read == 0 ? false : throw new EndOfStreamException("message cut short");
            read += n;
        }
        return true;
    }
}
