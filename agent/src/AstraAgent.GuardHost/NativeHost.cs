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
/// what kind of thing was found and how much, never the text. A "redact" request (D7) gets the
/// same text back with each finding replaced by a label; that goes only to the browser that
/// sent it, and never into an event. The host keeps nothing. It
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

    public sealed record Request(string? Type, string? Text, IReadOnlyList<string>? Keywords, JsonElement? Event = null,
                                 IReadOnlyList<string>? Keep = null, string? Site = null, string? Channel = null,
                                 string? Name = null, string? Data = null);

    /// <summary>D7: this account's approvals, as the service wrote them. Tests replace it.</summary>
    public static Func<IReadOnlyList<string>?> ReadApprovals { get; set; } = ApprovalsForThisAccount;

    static IReadOnlyList<string>? ApprovalsForThisAccount()
    {
        if (!OperatingSystem.IsWindows()) return null;
        try
        {
            var sid = System.Security.Principal.WindowsIdentity.GetCurrent().User?.Value;
            if (sid is null) return null;
            using var key = Microsoft.Win32.Registry.LocalMachine.OpenSubKey($@"{GuardApprovals.KeyPath}\{sid}");
            return key?.GetValue(GuardApprovals.ValueName) as string[];
        }
        catch (Exception ex) when (ex is System.Security.SecurityException or UnauthorizedAccessException or IOException)
        {
            return null;
        }
    }

    public sealed record Response(
        bool Ok,
        string? Error = null,
        IReadOnlyDictionary<string, int>? Counts = null,
        bool ContactList = false,
        IReadOnlyList<int>? KeywordHits = null,
        bool Truncated = false,
        bool Incomplete = false,
        string? Redacted = null,
        bool? Approved = null);

    /// <summary>Serve one connection until the browser closes stdin. <paramref name="forward"/>
    /// hands an event to the SAVIO service; tests replace it.</summary>
    public static async Task RunAsync(Stream input, Stream output, CancellationToken ct = default,
                                      Func<GuardEvent, CancellationToken, Task<bool>>? forward = null)
    {
        forward ??= EventPipe.SendAsync;
        while (!ct.IsCancellationRequested)
        {
            var frame = await ReadFrameAsync(input, ct);
            if (frame is null)
                return;                                   // the browser disconnected
            await WriteFrameAsync(output, await HandleAsync(frame, forward, ct), ct);
        }
    }

    /// <summary>
    /// Requests: "scan" (text in, counts out), "scan_file" (a document in, counts out) and "event" (E3: what the extension decided,
    /// passed on to the service). An event is parsed into the fixed <see cref="GuardEvent"/>
    /// shape and re-serialized from it, so whatever else the extension put in the message
    /// is dropped here and never reaches the pipe.
    /// </summary>
    public static async Task<Response> HandleAsync(byte[] frame, Func<GuardEvent, CancellationToken, Task<bool>> forward,
                                                   CancellationToken ct)
    {
        Request? req;
        try { req = JsonSerializer.Deserialize<Request>(frame, Json); }
        catch (JsonException) { return new Response(false, "malformed request"); }
        if (req?.Type == "event")
        {
            var e = req.Event is { ValueKind: JsonValueKind.Object } el ? GuardEvent.Parse(JsonSerializer.SerializeToUtf8Bytes(el)) : null;
            if (e is null) return new Response(false, "malformed event");
            return await forward(e, ct) ? new Response(true) : new Response(false, "not delivered");
        }
        return Handle(req);
    }

    public static Response Handle(byte[] frame)
    {
        Request? req;
        try { req = JsonSerializer.Deserialize<Request>(frame, Json); }
        catch (JsonException) { return new Response(false, "malformed request"); }
        return Handle(req);
    }

    static Response Handle(Request? req)
    {
        if (req?.Type == "approved")
        {
            // D7: has IT let this account through on this site, for this channel, right now?
            if (string.IsNullOrEmpty(req.Site) || string.IsNullOrEmpty(req.Channel))
                return new Response(false, "malformed request");
            return new Response(true, Approved: GuardApprovals.Allows(ReadApprovals(), req.Site, req.Channel, DateTimeOffset.UtcNow));
        }
        if (req?.Type == "redact")
        {
            // D7: the same text back with findings replaced by labels, for this browser only.
            var keep = (req.Keep ?? []).Select(k => Enum.TryParse<Finding>(k, out var f) ? f : (Finding?)null)
                                       .OfType<Finding>().ToArray();
            var redacted = PiiScanner.Redact(req.Text, req.Keywords, keep);
            return redacted is null ? new Response(false, "could not redact") : new Response(true, Redacted: redacted);
        }
        var text = req?.Text;
        if (req?.Type == "scan_file")
        {
            // A document the person is uploading (Word, Excel, PDF), as base64: scanned like
            // text, answered with counts only. The extension sends a PDF only where the org
            // chose to read them. Unreadable is an error, which the extension treats as
            // "could not check".
            var ext = Path.GetExtension(req.Name ?? "");
            byte[]? bytes;
            try { bytes = Convert.FromBase64String(req.Data ?? ""); }
            catch (FormatException) { bytes = null; }
            text = bytes is null ? null : Documents.Text(bytes, ext, pdf: true);
            if (text is null) return new Response(false, "could not read the document");
        }
        else if (req?.Type != "scan")
            return new Response(false, "unknown request");

        var r = PiiScanner.Scan(text, req.Keywords);
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
