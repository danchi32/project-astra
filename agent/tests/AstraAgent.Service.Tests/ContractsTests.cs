using System.Text.Json;
using AstraAgent.Service.Api;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>The backend API speaks snake_case; these tests pin the wire format.</summary>
public class ContractsTests
{
    [Fact]
    public void EnrollRequest_SerializesToSnakeCase()
    {
        var json = JsonSerializer.Serialize(new EnrollRequest(
            "tok", "HOST-1", "machine-1", "Windows 11", "SN1", "0.1.0"));
        Assert.Contains("\"enrollment_token\":", json);
        Assert.Contains("\"machine_id\":", json);
        Assert.Contains("\"os_version\":", json);
        Assert.Contains("\"serial_number\":", json);
        Assert.Contains("\"agent_version\":", json);
    }

    [Fact]
    public void EnrollResponse_DeserializesFromSnakeCase()
    {
        var id = Guid.NewGuid();
        var response = JsonSerializer.Deserialize<EnrollResponse>(
            $"{{\"device_id\":\"{id}\",\"device_token\":\"secret\"}}");
        Assert.NotNull(response);
        Assert.Equal(id, response.DeviceId);
        Assert.Equal("secret", response.DeviceToken);
    }

    [Fact]
    public void HeartbeatRequest_SerializesToSnakeCase()
    {
        var json = JsonSerializer.Serialize(new HeartbeatRequest("0.1.0", "ACME\\jdoe"));
        Assert.Contains("\"agent_version\":", json);
        Assert.Contains("\"logged_in_user\":", json);
    }
}
