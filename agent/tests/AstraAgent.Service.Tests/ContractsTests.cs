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

    [Fact]
    public void HeartbeatRequest_AsksForTasksByDefault()
    {
        // The whole point of the change: without this flag the backend keeps withholding
        // tasks (it must, for older agents), and this agent would never receive any work
        // now that its separate poll is gone.
        var json = JsonSerializer.Serialize(new HeartbeatRequest("0.7.0", null));
        Assert.Contains("\"include_tasks\":true", json);
    }

    [Fact]
    public void HeartbeatResponse_DeserializesTasks()
    {
        var id = Guid.NewGuid();
        var body = $$"""
        {"status":"ok","tasks":[{"id":"{{id}}","action_id":"clear_system_temp","params":null}]}
        """;
        var response = JsonSerializer.Deserialize<HeartbeatResponse>(body);
        Assert.NotNull(response);
        Assert.Single(response.Tasks!);
        Assert.Equal(id, response.Tasks![0].Id);
        Assert.Equal("clear_system_temp", response.Tasks[0].ActionId);
    }

    [Fact]
    public void HeartbeatResponse_ToleratesABackendWithoutTasks()
    {
        // An older backend replies {"status":"ok"} with no tasks field at all. That must
        // deserialize cleanly to "nothing to do" rather than throwing, or every heartbeat
        // against it would look like a failure and trigger pointless re-enrollment.
        var response = JsonSerializer.Deserialize<HeartbeatResponse>("""{"status":"ok"}""");
        Assert.NotNull(response);
        Assert.Null(response.Tasks);
    }
}
