using System.Net;
using AstraAgent.Service.Api;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>Only the backend's explicit "organization inactive" refusal may put a device to
/// sleep. Any other 403 or error is an ordinary failure: going dormant on one would silence a
/// paying customer's device for an hour at a time.</summary>
public class SubscriptionStateTests
{
    private static HttpResponseMessage Response(HttpStatusCode status, string? header = null)
    {
        var response = new HttpResponseMessage(status);
        if (header is not null)
            response.Headers.Add("X-Subscription-Status", header);
        return response;
    }

    [Fact]
    public void A_forbidden_with_the_inactive_header_is_the_dormant_signal()
    {
        using var response = Response(HttpStatusCode.Forbidden, "inactive");
        Assert.True(SubscriptionState.IsInactiveResponse(response));
    }

    [Fact]
    public void The_header_value_is_matched_case_insensitively()
    {
        using var response = Response(HttpStatusCode.Forbidden, "Inactive");
        Assert.True(SubscriptionState.IsInactiveResponse(response));
    }

    [Theory]
    [InlineData(HttpStatusCode.Forbidden, null)]          // some other 403
    [InlineData(HttpStatusCode.Forbidden, "active")]
    [InlineData(HttpStatusCode.OK, "inactive")]           // header on a success means nothing
    [InlineData(HttpStatusCode.Unauthorized, "inactive")] // credential problem, not billing
    [InlineData(HttpStatusCode.InternalServerError, null)]
    public void Anything_else_is_not(HttpStatusCode status, string? header)
    {
        using var response = Response(status, header);
        Assert.False(SubscriptionState.IsInactiveResponse(response));
    }

    [Fact]
    public void Set_flips_the_in_memory_state_both_ways()
    {
        var state = new SubscriptionState();
        Assert.False(state.Dormant);
        state.Set(true);
        Assert.True(state.Dormant);
        state.Set(false);
        Assert.False(state.Dormant);
    }
}
