using System.IO.Pipes;
using System.Security.Principal;
using System.Text;
using AstraAgent.Guard;
using AstraAgent.GuardHost;
using AstraAgent.Service.Api;
using AstraAgent.Service.Guard;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3 · E3: the event path from the native host to the backend.
/// <list type="bullet">
/// <item>The schema is fixed: no text, nothing extra.</item>
/// <item>The person is the one Windows names, not one the message names.</item>
/// <item>The queue is bounded, and a batch is dropped only once the backend has it.</item>
/// </list>
/// </summary>
public class GuardEventTests
{
    const string Valid = """
        {"site":"chatgpt.com","channel":"paste","mode":"warn","action":"warn",
         "counts":{"Pan":2,"Email":1},"contact_list":false,"keyword_hits":1,"unknown":false}
        """;

    static byte[] B(string s) => Encoding.UTF8.GetBytes(s);

    [Fact]
    public void The_schema_is_fixed()
    {
        var e = GuardEvent.Parse(B(Valid));
        Assert.NotNull(e);
        Assert.Equal(2, e.Counts["Pan"]);
        Assert.True(e.Notable);

        Assert.Null(GuardEvent.Parse(B(Valid.Replace("\"unknown\":false", "\"unknown\":false,\"text\":\"ABCPE1234F\""))));
        Assert.Null(GuardEvent.Parse(B(Valid.Replace("chatgpt.com", "chatgpt.com/c/123?q=secret"))));
        Assert.Null(GuardEvent.Parse(B(Valid.Replace("chatgpt.com", "My Secret Notes"))));
        Assert.Null(GuardEvent.Parse(B(Valid.Replace("\"paste\"", "\"clipboard\""))));
        Assert.Null(GuardEvent.Parse(B(Valid.Replace("\"Pan\"", "\"PasswordList\""))));
        Assert.Null(GuardEvent.Parse(B(Valid.Replace("\"keyword_hits\":1", "\"keyword_hits\":-1"))));
        Assert.Null(GuardEvent.Parse(B("not json")));
        Assert.Null(GuardEvent.Parse(new byte[GuardEvent.MaxBytes + 1]));
        Assert.NotNull(GuardEvent.Parse(B(Valid.Replace("chatgpt.com", "intranet"))));   // a name without a dot

        // D7: an answer to a prompt, with a reason from the list only after "justify".
        var justify = Valid.Replace("\"mode\":\"warn\",\"action\":\"warn\"", "\"mode\":\"justify\",\"action\":\"justify\"");
        Assert.NotNull(GuardEvent.Parse(B(justify.Replace("\"unknown\":false", "\"unknown\":false,\"outcome\":\"proceeded\",\"reason\":\"approved\""))));
        Assert.Null(GuardEvent.Parse(B(justify.Replace("\"unknown\":false", "\"unknown\":false,\"outcome\":\"proceeded\",\"reason\":\"because I said so\""))));
        Assert.Null(GuardEvent.Parse(B(justify.Replace("\"unknown\":false", "\"unknown\":false,\"outcome\":\"proceeded\""))));
        Assert.NotNull(GuardEvent.Parse(B(Valid.Replace("\"unknown\":false", "\"unknown\":false,\"outcome\":\"cancelled\""))));
        Assert.Null(GuardEvent.Parse(B(Valid.Replace("\"unknown\":false", "\"unknown\":false,\"outcome\":\"cancelled\",\"reason\":\"approved\""))));
        Assert.Null(GuardEvent.Parse(B(Valid.Replace("\"action\":\"warn\"", "\"action\":\"block\"").Replace("\"unknown\":false", "\"unknown\":false,\"outcome\":\"proceeded\""))));

        var nothing = GuardEvent.Parse(B("""{"site":"x.in","channel":"submit","mode":"log","action":"allow","counts":{},"contact_list":false,"keyword_hits":0,"unknown":false}"""));
        Assert.False(nothing!.Notable);
    }

    [Fact]
    public async Task The_host_forwards_only_the_fixed_shape()
    {
        var forwarded = new List<GuardEvent>();
        Task<bool> Forward(GuardEvent e, CancellationToken _) { forwarded.Add(e); return Task.FromResult(true); }

        var ok = await NativeHost.HandleAsync(B($$"""{"type":"event","event":{{Valid}}}"""), Forward, default);
        Assert.True(ok.Ok);
        Assert.Equal("chatgpt.com", Assert.Single(forwarded).Site);

        // Text smuggled into the event is refused, not passed on.
        var smuggled = Valid.Replace("\"unknown\":false", "\"unknown\":false,\"text\":\"ABCPE1234F\"");
        var refused = await NativeHost.HandleAsync(B($$"""{"type":"event","event":{{smuggled}}}"""), Forward, default);
        Assert.Equal("malformed event", refused.Error);
        Assert.Single(forwarded);

        var notDelivered = await NativeHost.HandleAsync(B($$"""{"type":"event","event":{{Valid}}}"""),
            (_, _) => Task.FromResult(false), default);
        Assert.Equal("not delivered", notDelivered.Error);
    }

    static GuardEventPipeServer Server(GuardEventQueue q) =>
        new(q, NullLogger<GuardEventPipeServer>.Instance) { Name = "SAVIO.Test." + Guid.NewGuid().ToString("N"), Security = () => null };

    static async Task<bool> Send(GuardEventPipeServer server, byte[] payload, TokenImpersonationLevel level)
    {
        await using var pipe = server.Create();
        var connected = pipe.WaitForConnectionAsync();
        await using var client = new NamedPipeClientStream(".", server.Name, PipeDirection.Out, PipeOptions.Asynchronous, level);
        await client.ConnectAsync(2000);
        await connected;
        var handled = server.HandleAsync(pipe, default);
        await client.WriteAsync(payload);
        await client.FlushAsync();
        client.Dispose();
        return await handled;
    }

    [Fact]
    public async Task The_service_takes_the_person_from_windows()
    {
        var q = new GuardEventQueue();
        var server = Server(q);
        Assert.True(await Send(server, B(Valid), TokenImpersonationLevel.Identification));
        var queued = Assert.Single(q.Peek(10));
        Assert.Equal(WindowsIdentity.GetCurrent().Name, queued.WindowsUser);
        Assert.Equal("chatgpt.com", queued.Event.Site);

        // Not identified (anonymous): cannot be attributed, not taken.
        Assert.False(await Send(server, B(Valid), TokenImpersonationLevel.Anonymous));
        // Junk, or an ordinary paste with nothing found: not taken.
        Assert.False(await Send(server, B("""{"text":"hello"}"""), TokenImpersonationLevel.Identification));
        Assert.Equal(1, q.Count);
    }

    static QueuedGuardEvent At(DateTime t) => new(t, @"PC\asha", GuardEvent.Parse(B(Valid))!);

    [Fact]
    public void The_queue_is_bounded()
    {
        var q = new GuardEventQueue();
        var t = new DateTime(2026, 11, 17, 10, 0, 0, DateTimeKind.Utc);
        for (var i = 0; i < GuardEventQueue.PerMinute + 5; i++) q.TryAdd(At(t.AddSeconds(i % 60)));
        Assert.Equal(GuardEventQueue.PerMinute, q.Count);
        Assert.Equal(5, q.Dropped);
        Assert.True(q.TryAdd(At(t.AddMinutes(1))));                      // a new minute

        q.Remove(10);
        Assert.Equal(GuardEventQueue.PerMinute - 9, q.Count);

        var full = new GuardEventQueue();
        for (var i = 0; i < GuardEventQueue.Capacity + 1; i++) full.TryAdd(At(t.AddMinutes(i)));
        Assert.Equal(GuardEventQueue.Capacity, full.Count);
        Assert.Equal(t, full.Peek(1)[0].At);                              // the oldest kept, the newest dropped
    }

    [Fact]
    public void The_queue_survives_a_restart()
    {
        var file = Path.Combine(Path.GetTempPath(), "savio-guard-q-" + Guid.NewGuid().ToString("N") + ".jsonl");
        try
        {
            var t = new DateTime(2026, 11, 17, 10, 0, 0, DateTimeKind.Utc);
            var q = new GuardEventQueue(file);
            for (var i = 0; i < 3; i++) q.TryAdd(At(t.AddMinutes(i)));
            q.Remove(1);
            File.AppendAllText(file, "{\"torn line\n" + """{"at":"2026-11-17T10:09:00Z","windows_user":"x","event":{"site":"x.in","text":"secret"}}""" + "\n");

            var again = new GuardEventQueue(file);                     // the service restarted
            Assert.Equal(2, again.Count);
            Assert.Equal(t.AddMinutes(1), again.Peek(1)[0].At);
            Assert.Equal(@"PC\asha", again.Peek(1)[0].WindowsUser);
            again.Remove(2);
            Assert.Equal(0, new GuardEventQueue(file).Count);
        }
        finally { File.Delete(file); }
    }

    [Fact]
    public async Task The_uploader_drops_a_batch_only_once_the_backend_has_it()
    {
        var q = new GuardEventQueue();
        var t = new DateTime(2026, 11, 17, 10, 0, 0, DateTimeKind.Utc);
        for (var i = 0; i < 3; i++) q.TryAdd(At(t.AddMinutes(i)));
        var api = new BrowserPolicyWorkerTests.Api { EventsAccepted = false };
        var enrollment = new BrowserPolicyWorkerTests.Enrollment();
        var subscription = new SubscriptionState();
        var up = new GuardEventUploader(q, enrollment, api, subscription, NullLogger<GuardEventUploader>.Instance);

        await up.RunOnceAsync(default);
        Assert.Equal(3, api.EventBatches.Single().Count);
        Assert.Equal(3, q.Count);                                         // backend down: kept

        api.EventsAccepted = true;
        await up.RunOnceAsync(default);
        Assert.Equal(0, q.Count);

        await up.RunOnceAsync(default);
        Assert.Equal(2, api.EventBatches.Count);                         // nothing queued: nothing sent

        q.TryAdd(At(t.AddHours(1)));
        enrollment.Token = null;                                          // not enrolled
        await up.RunOnceAsync(default);
        Assert.Equal(2, api.EventBatches.Count);
    }
}
