using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using AstraAgent.Service.Update;

namespace AstraAgent.Service.Api;

public enum HeartbeatStatus
{
    Ok,
    Unauthorized,
    Failed,
}

public interface IAstraApiClient
{
    Task<EnrollResponse?> EnrollAsync(EnrollRequest request, CancellationToken ct);
    Task<HeartbeatStatus> HeartbeatAsync(string deviceToken, HeartbeatRequest request, CancellationToken ct);
    Task<bool> PushTelemetryAsync(string deviceToken, TelemetryPush payload, CancellationToken ct);

    /// <summary>Ask the backend for the current signed update manifest. Returns null on any
    /// transport error; an envelope with Available=false means no channel is configured.</summary>
    Task<UpdateEnvelope?> GetUpdateAsync(string deviceToken, CancellationToken ct);
}

public sealed class AstraApiClient(HttpClient http, ILogger<AstraApiClient> logger) : IAstraApiClient
{
    public async Task<EnrollResponse?> EnrollAsync(EnrollRequest request, CancellationToken ct)
    {
        var response = await http.PostAsJsonAsync("/api/v1/agent/enroll", request, ct);
        if (!response.IsSuccessStatusCode)
        {
            logger.LogError("Enrollment rejected with status {Status}", response.StatusCode);
            return null;
        }
        return await response.Content.ReadFromJsonAsync<EnrollResponse>(ct);
    }

    public async Task<bool> PushTelemetryAsync(string deviceToken, TelemetryPush payload, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/telemetry")
        {
            Content = JsonContent.Create(payload),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        var response = await http.SendAsync(message, ct);
        if (!response.IsSuccessStatusCode)
            logger.LogWarning("Telemetry push failed with status {Status}", response.StatusCode);
        return response.IsSuccessStatusCode;
    }

    public async Task<UpdateEnvelope?> GetUpdateAsync(string deviceToken, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Get, "/api/v1/agent/update");
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            if (!response.IsSuccessStatusCode)
                return null;
            return await response.Content.ReadFromJsonAsync<UpdateEnvelope>(ct);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return null;   // offline / timeout — try again next cycle
        }
    }

    public async Task<HeartbeatStatus> HeartbeatAsync(
        string deviceToken, HeartbeatRequest request, CancellationToken ct)
    {
        // The device token is attached per request, never on the shared client,
        // because it can rotate after a re-enrollment.
        using var message = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/heartbeat")
        {
            Content = JsonContent.Create(request),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);

        var response = await http.SendAsync(message, ct);
        if (response.StatusCode == HttpStatusCode.Unauthorized)
            return HeartbeatStatus.Unauthorized;
        if (!response.IsSuccessStatusCode)
        {
            logger.LogWarning("Heartbeat failed with status {Status}", response.StatusCode);
            return HeartbeatStatus.Failed;
        }
        return HeartbeatStatus.Ok;
    }
}
