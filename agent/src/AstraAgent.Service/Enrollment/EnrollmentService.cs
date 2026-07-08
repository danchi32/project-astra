using AstraAgent.Service.Api;
using AstraAgent.Service.Security;
using Microsoft.Extensions.Options;

namespace AstraAgent.Service.Enrollment;

public interface IEnrollmentService
{
    /// <summary>Returns the stored device credential, enrolling first if needed.
    /// Null when enrollment is impossible (no enrollment token configured or server rejected it).</summary>
    Task<string?> GetDeviceTokenAsync(CancellationToken ct);

    /// <summary>Discards the stored credential and enrolls again — used after the
    /// server rejects the current credential.</summary>
    Task<string?> ReEnrollAsync(CancellationToken ct);
}

public sealed class EnrollmentService(
    IAstraApiClient api,
    ITokenStore store,
    IDeviceIdentityProvider identity,
    IOptions<AgentOptions> options,
    ILogger<EnrollmentService> logger) : IEnrollmentService
{
    // The heartbeat and telemetry workers both request the credential concurrently.
    // Serialise enrollment so only one HTTP enroll happens; the other waits and
    // then reuses the freshly stored token instead of racing a second enroll.
    private readonly SemaphoreSlim _gate = new(1, 1);

    public async Task<string?> GetDeviceTokenAsync(CancellationToken ct)
    {
        var stored = store.Load();
        if (stored is not null)
            return stored;
        return await EnrollAsync(ct);
    }

    public async Task<string?> ReEnrollAsync(CancellationToken ct)
    {
        await _gate.WaitAsync(ct);
        try
        {
            store.Clear();
            return await EnrollLockedAsync(ct);
        }
        finally
        {
            _gate.Release();
        }
    }

    private async Task<string?> EnrollAsync(CancellationToken ct)
    {
        await _gate.WaitAsync(ct);
        try
        {
            // Double-check: another worker may have enrolled while we waited.
            var stored = store.Load();
            if (stored is not null)
                return stored;
            return await EnrollLockedAsync(ct);
        }
        finally
        {
            _gate.Release();
        }
    }

    private async Task<string?> EnrollLockedAsync(CancellationToken ct)
    {
        var enrollmentToken = options.Value.EnrollmentToken;
        if (string.IsNullOrWhiteSpace(enrollmentToken))
        {
            logger.LogError(
                "Device is not enrolled and no enrollment token is configured (Astra:EnrollmentToken)");
            return null;
        }

        var device = identity.Collect();
        logger.LogInformation(
            "Enrolling device {Hostname} (machine {MachineId})", device.Hostname, device.MachineId);

        var response = await api.EnrollAsync(
            new EnrollRequest(
                enrollmentToken,
                device.Hostname,
                device.MachineId,
                device.OsVersion,
                device.SerialNumber,
                AgentVersion.Current),
            ct);
        if (response is null)
            return null;

        store.Save(response.DeviceToken);
        logger.LogInformation("Enrolled as device {DeviceId}", response.DeviceId);
        return response.DeviceToken;
    }
}
