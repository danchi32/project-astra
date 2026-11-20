using System.Buffers.Binary;
using System.Text;
using System.Text.Json;
using AstraAgent.GuardHost;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>Phase 3 · D3 native messaging host: the browser's framing, and an answer that holds
/// counts and never the text it was given.</summary>
public class NativeHostTests
{
    static byte[] Frame(string json)
    {
        var body = Encoding.UTF8.GetBytes(json);
        var buf = new byte[4 + body.Length];
        BinaryPrimitives.WriteInt32LittleEndian(buf, body.Length);
        body.CopyTo(buf, 4);
        return buf;
    }

    static async Task<List<JsonElement>> Converse(params string[] requests)
    {
        var input = new MemoryStream(requests.SelectMany(Frame).ToArray());
        var output = new MemoryStream();
        await NativeHost.RunAsync(input, output);
        output.Position = 0;
        var answers = new List<JsonElement>();
        while (await NativeHost.ReadFrameAsync(output, default) is { } frame)
            answers.Add(JsonDocument.Parse(frame).RootElement.Clone());
        return answers;
    }

    [Fact]
    public async Task Scans_and_answers_with_counts_only()
    {
        const string secret = "PAN ABCPE1234F and card 4111 1111 1111 1111, project falcon";
        var answers = await Converse(
            JsonSerializer.Serialize(new { type = "scan", text = secret, keywords = new[] { "project falcon" } }),
            """{"type":"scan","text":"nothing here"}""");

        Assert.Equal(2, answers.Count);
        var first = answers[0];
        Assert.True(first.GetProperty("ok").GetBoolean());
        Assert.Equal(1, first.GetProperty("counts").GetProperty("Pan").GetInt32());
        Assert.Equal(1, first.GetProperty("counts").GetProperty("PaymentCard").GetInt32());
        Assert.Equal(0, first.GetProperty("keyword_hits")[0].GetInt32());
        var raw = first.GetRawText();
        Assert.DoesNotContain("ABCPE1234F", raw);
        Assert.DoesNotContain("4111", raw);
        Assert.DoesNotContain("falcon", raw);
        Assert.Empty(answers[1].GetProperty("counts").EnumerateObject());
    }

    [Theory]
    [InlineData("not json", "malformed request")]
    [InlineData("""{"type":"exfiltrate"}""", "unknown request")]
    public async Task Refuses_what_it_does_not_understand(string request, string error)
    {
        var answer = (await Converse(request)).Single();
        Assert.False(answer.GetProperty("ok").GetBoolean());
        Assert.Equal(error, answer.GetProperty("error").GetString());
    }

    [Fact]
    public async Task An_oversized_or_cut_short_frame_ends_the_connection()
    {
        var huge = new byte[4];
        BinaryPrimitives.WriteInt32LittleEndian(huge, NativeHost.MaxRequestBytes + 1);
        await Assert.ThrowsAsync<InvalidDataException>(() => NativeHost.RunAsync(new MemoryStream(huge), new MemoryStream()));

        var cut = Frame("""{"type":"scan","text":"abc"}""")[..10];
        await Assert.ThrowsAsync<EndOfStreamException>(() => NativeHost.RunAsync(new MemoryStream(cut), new MemoryStream()));
    }

    [Fact]
    public async Task Redact_answers_with_the_text_findings_replaced()
    {
        var answer = (await Converse(JsonSerializer.Serialize(new
        {
            type = "redact", text = "PAN ABCPE1234F, mail a@b.in", keep = new[] { "Email", "NotAKind" },
        }))).Single();
        Assert.True(answer.GetProperty("ok").GetBoolean());
        Assert.Equal("PAN [PAN], mail a@b.in", answer.GetProperty("redacted").GetString());
    }

    [Fact]
    public async Task A_closed_stdin_ends_quietly()
    {
        Assert.Empty(await Converse());
    }
}
