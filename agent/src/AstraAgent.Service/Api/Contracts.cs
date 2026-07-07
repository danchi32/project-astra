using System.Text.Json.Serialization;

namespace AstraAgent.Service.Api;

public sealed record EnrollRequest(
    [property: JsonPropertyName("enrollment_token")] string EnrollmentToken,
    [property: JsonPropertyName("hostname")] string Hostname,
    [property: JsonPropertyName("machine_id")] string MachineId,
    [property: JsonPropertyName("os_version")] string OsVersion,
    [property: JsonPropertyName("serial_number")] string? SerialNumber,
    [property: JsonPropertyName("agent_version")] string AgentVersion);

public sealed record EnrollResponse(
    [property: JsonPropertyName("device_id")] Guid DeviceId,
    [property: JsonPropertyName("device_token")] string DeviceToken);

public sealed record HeartbeatRequest(
    [property: JsonPropertyName("agent_version")] string AgentVersion,
    [property: JsonPropertyName("logged_in_user")] string? LoggedInUser);
