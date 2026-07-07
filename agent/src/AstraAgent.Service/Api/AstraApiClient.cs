using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;

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
