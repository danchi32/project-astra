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
    // The backend refused because this device's organization is inactive. Not a failure to
    // back off from but a signal to go dormant (see SubscriptionState).
    Suspended,
}

/// <summary>Outcome of a heartbeat: its status, plus any system-context remediation the
/// backend handed back on the same call. Tasks are empty against a backend that predates
/// this, which is exactly the old behaviour — the Service simply gets nothing to run.</summary>
public sealed record HeartbeatResult(
    HeartbeatStatus Status,
    IReadOnlyList<AgentRemediationTask> Tasks,
    // Whether this org holds the Workforce Insights entitlement, as the backend reported on
    // this beat. Always false on a non-Ok result or an unreadable body — the safe default
    // for monitoring is "do not collect".
    bool ActivityTracking = false,
    // "domain" or "path" — how much of a browser URL to record. Defaults to "domain".
    string ActivityUrlMode = "domain")
{
    public static HeartbeatResult From(HeartbeatStatus status) => new(status, []);
}

public interface IAstraApiClient
{
    Task<EnrollResponse?> EnrollAsync(EnrollRequest request, CancellationToken ct);
    Task<HeartbeatResult> HeartbeatAsync(string deviceToken, HeartbeatRequest request, CancellationToken ct);
    Task<bool> PushTelemetryAsync(string deviceToken, TelemetryPush payload, CancellationToken ct);
    Task<bool> PushOfflineEventsAsync(string deviceToken, IReadOnlyList<Net.JournalEntry> entries, CancellationToken ct);

    /// <summary>Escrow BitLocker recovery passwords. False on any failure, including a server
    /// without an encryption key (503): the caller keeps the keys and tries again next hour.</summary>
    Task<bool> EscrowBitLockerKeysAsync(
        string deviceToken, IReadOnlyList<Telemetry.Collectors.BitLockerRecoveryKey> keys, CancellationToken ct);

    /// <summary>Ask the backend for the current signed update manifest. Returns null on any
    /// transport error; an envelope with Available=false means no channel is configured.</summary>
    Task<UpdateEnvelope?> GetUpdateAsync(string deviceToken, CancellationToken ct);

    /// <summary>What this device should do about remote support. Null on any failure —
    /// the caller then does nothing, which is the safe answer: an unreachable backend
    /// must not be read as "uninstall", or a relay outage would strip remote support
    /// from a whole fleet.</summary>
    Task<RemoteSupportPlan?> GetRemoteSupportPlanAsync(string deviceToken, CancellationToken ct);

    /// <summary>Claim approved remediation tasks for the given execution context ("system"
    /// for the elevated Service). The backend marks the returned tasks dispatched. Returns
    /// null on Unauthorized (credential rotated), an empty list when there's nothing to do.</summary>
    Task<IReadOnlyList<AgentRemediationTask>?> ClaimTasksAsync(
        string deviceToken, string context, CancellationToken ct);

    /// <summary>Report the outcome of a remediation task back to the backend.</summary>
    Task<bool> ReportTaskResultAsync(
        string deviceToken, Guid taskId, AgentRemediationResult result, CancellationToken ct);

    /// <summary>D10: the browser policy to apply. Null on any failure, which the caller reads
    /// as "keep what you have", never as "remove everything".</summary>
    Task<AgentBrowserPolicy?> GetBrowserPolicyAsync(string deviceToken, CancellationToken ct);

    /// <summary>D10: what applying it did, per browser, and how many times each other browser
    /// was closed since the last report.</summary>
    Task<bool> ReportBrowserPolicyAsync(
        string deviceToken, int version, IReadOnlyList<Guard.ApplyReport> reports,
        IReadOnlyDictionary<string, int> closed, IReadOnlyList<Guard.SeenDrive> drives, CancellationToken ct);

    /// <summary>E3: a batch of extension events (counts only). True when the backend has them,
    /// or refused them for good, so the caller can drop the batch.</summary>
    Task<bool> SendGuardEventsAsync(string deviceToken, IReadOnlyList<Guard.QueuedGuardEvent> events, CancellationToken ct);

    /// <summary>D7: the approvals in force on this PC. Null on any failure (keep what is stored;
    /// each approval ends at its own time anyway).</summary>
    Task<IReadOnlyList<AgentGuardApproval>?> GetGuardApprovalsAsync(string deviceToken, CancellationToken ct);

    /// <summary>D5: this PC's map of where sensitive files are (folder counts only).</summary>
    Task<bool> SendDiscoveryAsync(string deviceToken, DateTime scannedAtUtc, DiscoveryReport report, CancellationToken ct);

    /// <summary>C3: the USB write window open for this PC. Null on any failure (keep what is
    /// known; a window ends at its own time anyway).</summary>
    Task<AgentUsbWindow?> GetUsbWindowAsync(string deviceToken, CancellationToken ct);

    /// <summary>C3b: the person at this PC asks IT for a USB write window. The HTTP status, or 0
    /// when the backend could not be reached.</summary>
    Task<int> RequestUsbWriteAsync(string deviceToken, string windowsUser, string reason, CancellationToken ct);
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

    /// <summary>B1 — what the offline self-heal did while SAVIO was unreachable, for the audit log.</summary>
    public async Task<bool> PushOfflineEventsAsync(
        string deviceToken, IReadOnlyList<Net.JournalEntry> entries, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/offline-events")
        {
            Content = JsonContent.Create(new { events = entries.Select(e => new
            {
                at = e.At, trigger = e.Trigger, diagnosis = e.Diagnosis, step = e.Step,
                step_ok = e.StepOk, output = e.Output, fixed_after = e.FixedAfter,
            }) }),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException) { return false; }
        catch (TaskCanceledException) when (!ct.IsCancellationRequested) { return false; }
    }

    public async Task<bool> EscrowBitLockerKeysAsync(
        string deviceToken, IReadOnlyList<Telemetry.Collectors.BitLockerRecoveryKey> keys, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/bitlocker-keys")
        {
            Content = JsonContent.Create(new { keys = keys.Select(k => new
            {
                drive = k.Drive, protector_id = k.ProtectorId, recovery_password = k.RecoveryPassword,
            }) }),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException) { return false; }
        catch (TaskCanceledException) when (!ct.IsCancellationRequested) { return false; }
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

    public async Task<RemoteSupportPlan?> GetRemoteSupportPlanAsync(
        string deviceToken, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Get, "/api/v1/agent/remote-support");
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            // A backend too old to know this endpoint answers 404. Null, not "disabled":
            // the difference is doing nothing versus uninstalling a working agent.
            if (!response.IsSuccessStatusCode)
                return null;
            return await response.Content.ReadFromJsonAsync<RemoteSupportPlan>(ct);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return null;   // offline / timeout — try again next cycle
        }
    }

    public async Task<IReadOnlyList<AgentRemediationTask>?> ClaimTasksAsync(
        string deviceToken, string context, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(
            HttpMethod.Get, $"/api/v1/agent/tasks?context={Uri.EscapeDataString(context)}");
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            if (response.StatusCode == HttpStatusCode.Unauthorized)
                return null;
            if (!response.IsSuccessStatusCode)
            {
                logger.LogWarning("Task claim failed with status {Status}", response.StatusCode);
                return Array.Empty<AgentRemediationTask>();
            }
            return await response.Content.ReadFromJsonAsync<List<AgentRemediationTask>>(ct)
                   ?? (IReadOnlyList<AgentRemediationTask>)Array.Empty<AgentRemediationTask>();
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return Array.Empty<AgentRemediationTask>();   // offline / timeout — retry next cycle
        }
    }

    public async Task<bool> ReportTaskResultAsync(
        string deviceToken, Guid taskId, AgentRemediationResult result, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(
            HttpMethod.Post, $"/api/v1/agent/tasks/{taskId}/result")
        {
            Content = JsonContent.Create(result),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        var response = await http.SendAsync(message, ct);
        if (!response.IsSuccessStatusCode)
            logger.LogWarning("Task result report failed with status {Status}", response.StatusCode);
        return response.IsSuccessStatusCode;
    }

    public async Task<HeartbeatResult> HeartbeatAsync(
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
            return HeartbeatResult.From(HeartbeatStatus.Unauthorized);
        if (SubscriptionState.IsInactiveResponse(response))
            return HeartbeatResult.From(HeartbeatStatus.Suspended);
        if (!response.IsSuccessStatusCode)
        {
            logger.LogWarning("Heartbeat failed with status {Status}", response.StatusCode);
            return HeartbeatResult.From(HeartbeatStatus.Failed);
        }

        // A body that can't be read must not fail the beat: liveness was already recorded
        // server-side, and treating it as a failure would trigger a pointless re-enrollment.
        try
        {
            var body = await response.Content.ReadFromJsonAsync<HeartbeatResponse>(ct);
            return new HeartbeatResult(
                HeartbeatStatus.Ok, body?.Tasks ?? [], body?.ActivityTracking ?? false,
                body?.ActivityUrlMode ?? "domain");
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            logger.LogWarning(ex, "Heartbeat succeeded but its body could not be parsed");
            return HeartbeatResult.From(HeartbeatStatus.Ok);
        }
    }

    public async Task<int> RequestUsbWriteAsync(string deviceToken, string windowsUser, string reason, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/usb-request")
        {
            Content = JsonContent.Create(new { windows_user = windowsUser, reason }),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            return (int)(await http.SendAsync(message, ct)).StatusCode;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return 0;
        }
    }

    public async Task<AgentUsbWindow?> GetUsbWindowAsync(string deviceToken, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Get, "/api/v1/agent/usb-window");
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            return response.IsSuccessStatusCode ? await response.Content.ReadFromJsonAsync<AgentUsbWindow>(ct) : null;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or System.Text.Json.JsonException)
        {
            return null;
        }
    }

    public async Task<AgentBrowserPolicy?> GetBrowserPolicyAsync(string deviceToken, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Get, "/api/v1/agent/browser-policy");
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            // An older backend answers 404: null, so nothing already applied is taken away.
            if (!response.IsSuccessStatusCode)
                return null;
            return await response.Content.ReadFromJsonAsync<AgentBrowserPolicy>(ct);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or System.Text.Json.JsonException)
        {
            return null;
        }
    }

    public async Task<bool> ReportBrowserPolicyAsync(
        string deviceToken, int version, IReadOnlyList<Guard.ApplyReport> reports,
        IReadOnlyDictionary<string, int> closed, IReadOnlyList<Guard.SeenDrive> drives, CancellationToken ct)
    {
        var body = new Dictionary<string, object>
        {
            ["version"] = version,
            ["results"] = reports.Take(10).Select(r => new
            {
                browser = r.Browser.ToString(),
                set = r.Set.Take(50), repaired = r.Repaired.Take(50),
                removed = r.Removed.Take(50), conflicts = r.Conflicts.Take(50),
                error = r.Error is { Length: > 500 } e ? e[..500] : r.Error,
            }),
        };
        // Only when there is something: a backend from before D10's closing refuses the field.
        if (closed.Count > 0)
            body["closed"] = closed;
        // C3b: likewise only when there are some, for the same reason.
        if (drives.Count > 0)
            body["drives"] = drives.Take(50).Select(d => new { id = d.Id, name = d.Name, unique_serial = d.UniqueSerial });
        using var message = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/browser-policy/report")
        {
            Content = JsonContent.Create(body),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            logger.LogDebug(ex, "Browser policy report not sent");
            return false;
        }
    }

    public async Task<bool> SendGuardEventsAsync(
        string deviceToken, IReadOnlyList<Guard.QueuedGuardEvent> events, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/guard/events")
        {
            Content = JsonContent.Create(new
            {
                events = events.Select(q =>
                {
                    var e = new Dictionary<string, object?>
                    {
                        ["at"] = q.At, ["windows_user"] = q.WindowsUser,
                        ["site"] = q.Event.Site, ["channel"] = q.Event.Channel, ["mode"] = q.Event.Mode,
                        ["action"] = q.Event.Action, ["counts"] = q.Event.Counts, ["contact_list"] = q.Event.ContactList,
                        ["keyword_hits"] = q.Event.KeywordHits, ["unknown"] = q.Event.Unknown,
                        ["outcome"] = q.Event.Outcome, ["reason"] = q.Event.Reason,
                    };
                    // C2: only when known, so a backend from before C2 never sees the field.
                    if (q.Event.Origin is not null) e["origin"] = q.Event.Origin;
                    return e;
                }),
            }),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            // A 422 will never succeed on retry: drop the batch rather than block every later event.
            return response.IsSuccessStatusCode || (int)response.StatusCode == 422;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            logger.LogDebug(ex, "Guard events not sent");
            return false;
        }
    }

    public async Task<IReadOnlyList<AgentGuardApproval>?> GetGuardApprovalsAsync(string deviceToken, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Get, "/api/v1/agent/guard/approvals");
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            if (!response.IsSuccessStatusCode) return null;
            return await response.Content.ReadFromJsonAsync<List<AgentGuardApproval>>(ct);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or System.Text.Json.JsonException)
        {
            logger.LogDebug(ex, "Guard approvals not fetched");
            return null;
        }
    }

    public async Task<bool> SendDiscoveryAsync(string deviceToken, DateTime scannedAtUtc, DiscoveryReport report, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/guard/discovery")
        {
            Content = JsonContent.Create(new
            {
                scanned_at = scannedAtUtc, files_scanned = report.FilesScanned, files_skipped = report.FilesSkipped,
                truncated = report.Truncated, folders = report.Folders,
            }),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", deviceToken);
        try
        {
            var response = await http.SendAsync(message, ct);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            logger.LogDebug(ex, "Discovery map not sent");
            return false;
        }
    }
}
