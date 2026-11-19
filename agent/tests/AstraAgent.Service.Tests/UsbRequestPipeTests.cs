using System.IO.Pipes;
using System.Security.Principal;
using System.Text;
using AstraAgent.Service.Api;
using AstraAgent.Service.Guard;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3c · C3b: the tray asks the service for a USB write window. Only two requests, a reason
/// from a fixed list, the person from Windows, and only where the org's policy takes requests.
/// </summary>
public class UsbRequestPipeTests
{
    readonly BrowserPolicyWorkerTests.Api _api = new();
    readonly DateTime _now = new(2026, 11, 19, 10, 0, 0, DateTimeKind.Utc);

    async Task<UsbRequestPipeServer> Server(string usbMode, DateTimeOffset? windowUntil = null)
    {
        var policy = new BrowserPolicyWorker(new BrowserPolicyWorkerTests.Enrollment(), _api, new SubscriptionState(),
            Options.Create(new AgentOptions()), NullLogger<BrowserPolicyWorker>.Instance)
        { Apply = _ => [], StoreApprovals = _ => { }, Drives = () => [] };
        _api.Next = new AgentBrowserPolicy(3, new AgentBrowserPolicyBody(UsbMode: usbMode));
        _api.UsbWindow = new(windowUntil);
        await policy.RunOnceAsync(_now, default);
        return new UsbRequestPipeServer(policy, new BrowserPolicyWorkerTests.Enrollment(), _api,
                                        NullLogger<UsbRequestPipeServer>.Instance)
        { Name = "SAVIO.Test." + Guid.NewGuid().ToString("N"), Security = () => null };
    }

    [Fact]
    public async Task Status_tells_the_tray_what_to_show()
    {
        Assert.Equal("off", await (await Server("read_only")).AnswerAsync("status", () => null, _now, default));
        Assert.Equal("closed", await (await Server("on_request")).AnswerAsync("status", () => null, _now, default));
        var until = new DateTimeOffset(_now.AddMinutes(30));
        Assert.StartsWith("open:", await (await Server("on_request", until)).AnswerAsync("status", () => null, _now, default));
    }

    [Fact]
    public async Task A_request_goes_to_it_only_with_a_listed_reason_and_a_known_person()
    {
        var s = await Server("on_request");
        Assert.StartsWith("Request sent", await s.AnswerAsync("request:backup", () => @"ACME\ravi", _now, default));
        Assert.Equal((@"ACME\ravi", "backup"), Assert.Single(_api.UsbRequests));

        Assert.Equal("Unknown request.", await s.AnswerAsync("request:my boss said so", () => @"ACME\ravi", _now, default));
        Assert.Equal("Unknown request.", await s.AnswerAsync("open the drives", () => @"ACME\ravi", _now, default));
        Assert.StartsWith("SAVIO could not tell", await s.AnswerAsync("request:other", () => null, _now, default));
        _api.UsbRequestStatus = 0;
        Assert.StartsWith("SAVIO could not reach", await s.AnswerAsync("request:other", () => @"ACME\ravi", _now, default));
        Assert.Single(_api.UsbRequests, r => r.Reason == "backup");

        // Not in that mode, or already open: nothing is sent.
        _api.UsbRequests.Clear();
        await (await Server("block")).AnswerAsync("request:backup", () => @"ACME\ravi", _now, default);
        await (await Server("on_request", new DateTimeOffset(_now.AddMinutes(5)))).AnswerAsync("request:backup", () => @"ACME\ravi", _now, default);
        Assert.Empty(_api.UsbRequests);
    }

    [Fact]
    public async Task Over_the_pipe_the_person_comes_from_windows()
    {
        var s = await Server("on_request");
        await using var pipe = s.Create();
        var connected = pipe.WaitForConnectionAsync();
        await using var client = new NamedPipeClientStream(".", s.Name, PipeDirection.InOut, PipeOptions.Asynchronous,
                                                           TokenImpersonationLevel.Identification);
        await client.ConnectAsync(2000);
        await connected;
        var handled = s.HandleAsync(pipe, _now, default);
        await client.WriteAsync(Encoding.UTF8.GetBytes("request:presentation"));
        await client.FlushAsync();
        var buf = new byte[1024];
        var reply = Encoding.UTF8.GetString(buf, 0, await client.ReadAsync(buf));
        await handled;
        Assert.StartsWith("Request sent", reply);
        Assert.Equal(WindowsIdentity.GetCurrent().Name, Assert.Single(_api.UsbRequests).User);
    }
}
