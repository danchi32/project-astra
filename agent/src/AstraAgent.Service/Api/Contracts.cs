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

// ── Remediation (elevated / system-context tasks the Service executes) ───────

public sealed record AgentRemediationTask(
    [property: JsonPropertyName("id")] Guid Id,
    [property: JsonPropertyName("action_id")] string ActionId,
    [property: JsonPropertyName("params")] Dictionary<string, string>? Params);

public sealed record AgentRemediationResult(
    [property: JsonPropertyName("success")] bool Success,
    [property: JsonPropertyName("output")] string Output);

// ── Telemetry ──────────────────────────────────────────────────────────────

public sealed record TelemetryDiskInfo(
    [property: JsonPropertyName("drive")] string Drive,
    [property: JsonPropertyName("total_gb")] double TotalGb,
    [property: JsonPropertyName("used_gb")] double UsedGb,
    [property: JsonPropertyName("free_gb")] double FreeGb);

public sealed record TelemetryEventLogEntry(
    [property: JsonPropertyName("log_name")] string LogName,
    [property: JsonPropertyName("source")] string Source,
    [property: JsonPropertyName("event_id")] int EventId,
    [property: JsonPropertyName("level")] string Level,
    [property: JsonPropertyName("message")] string Message,
    [property: JsonPropertyName("occurred_at")] DateTimeOffset OccurredAt);

public sealed record TelemetryInstalledApp(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("version")] string? Version,
    [property: JsonPropertyName("publisher")] string? Publisher,
    [property: JsonPropertyName("install_date")] string? InstallDate);

public sealed record TelemetryServiceEntry(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("display_name")] string DisplayName,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("start_type")] string StartType);

public sealed record TelemetryWindowsUpdate(
    [property: JsonPropertyName("kb_article_id")] string KbArticleId,
    [property: JsonPropertyName("title")] string Title,
    [property: JsonPropertyName("is_installed")] bool IsInstalled,
    [property: JsonPropertyName("installed_on")] string? InstalledOn);

public sealed record TelemetryHardware(
    [property: JsonPropertyName("manufacturer")] string? Manufacturer,
    [property: JsonPropertyName("model")] string? Model,
    [property: JsonPropertyName("cpu_name")] string? CpuName,
    [property: JsonPropertyName("total_ram_mb")] long? TotalRamMb,
    [property: JsonPropertyName("total_storage_gb")] double? TotalStorageGb);

public sealed record TelemetryPush(
    [property: JsonPropertyName("collected_at")] DateTimeOffset CollectedAt,
    [property: JsonPropertyName("cpu_percent")] float CpuPercent,
    [property: JsonPropertyName("ram_total_mb")] long RamTotalMb,
    [property: JsonPropertyName("ram_used_mb")] long RamUsedMb,
    [property: JsonPropertyName("disks")] IReadOnlyList<TelemetryDiskInfo> Disks,
    [property: JsonPropertyName("hardware")] TelemetryHardware? Hardware,
    [property: JsonPropertyName("event_logs")] IReadOnlyList<TelemetryEventLogEntry> EventLogs,
    [property: JsonPropertyName("installed_apps")] IReadOnlyList<TelemetryInstalledApp> InstalledApps,
    [property: JsonPropertyName("services")] IReadOnlyList<TelemetryServiceEntry> Services,
    [property: JsonPropertyName("windows_updates")] IReadOnlyList<TelemetryWindowsUpdate> WindowsUpdates);
