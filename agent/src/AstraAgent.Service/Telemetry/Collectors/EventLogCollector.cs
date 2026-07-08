using System.Diagnostics;
using System.Diagnostics.Eventing.Reader;

namespace AstraAgent.Service.Telemetry.Collectors;

public sealed class EventLogCollector(ILogger<EventLogCollector> logger) : IEventLogCollector
{
    private static readonly string[] WatchedLogs = ["System", "Application"];

    public IReadOnlyList<EventLogEntry> GetRecentEntries(int maxEntries = 50)
    {
        var results = new List<EventLogEntry>();
        try
        {
            // Query errors and warnings from the last 24 hours across System + Application logs.
            var cutoff = DateTime.UtcNow.AddHours(-24);
            var query = new EventLogQuery(
                "*[System[(Level=1 or Level=2 or Level=3) and TimeCreated[timediff(@SystemTime) <= 86400000]]]",
                PathType.LogName);

            foreach (var logName in WatchedLogs)
            {
                if (results.Count >= maxEntries) break;
                try
                {
                    var logQuery = new EventLogQuery(logName, PathType.LogName,
                        "*[System[(Level=1 or Level=2) and TimeCreated[timediff(@SystemTime) <= 86400000]]]");
                    using var reader = new EventLogReader(logQuery);
                    EventRecord? record;
                    while ((record = reader.ReadEvent()) != null && results.Count < maxEntries)
                    {
                        using (record)
                        {
                            results.Add(new EventLogEntry(
                                logName,
                                record.ProviderName ?? "Unknown",
                                record.Id,
                                LevelName(record.Level),
                                TruncateMessage(record.FormatDescription() ?? string.Empty),
                                    ToOffset(record.TimeCreated)));
                        }
                    }
                }
                catch (Exception ex)
                {
                    logger.LogWarning(ex, "Could not read {LogName} event log", logName);
                }
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Event log collection failed");
        }
        return results;
    }

    /// <summary>EventRecord.TimeCreated is a local (or unspecified) DateTime; converting it
    /// to UTC first avoids the "UTC Offset does not match" exception that a naive
    /// DateTimeOffset(local, TimeSpan.Zero) construction throws.</summary>
    internal static DateTimeOffset ToOffset(DateTime? timeCreated)
    {
        if (!timeCreated.HasValue)
            return DateTimeOffset.UtcNow;

        var value = timeCreated.Value;
        var utc = value.Kind switch
        {
            DateTimeKind.Utc => value,
            // Treat Unspecified as local time, which is how the event log reports it.
            _ => DateTime.SpecifyKind(value, DateTimeKind.Local).ToUniversalTime(),
        };
        return new DateTimeOffset(utc, TimeSpan.Zero);
    }

    private static string LevelName(byte? level) => level switch
    {
        1 => "Critical",
        2 => "Error",
        3 => "Warning",
        _ => "Information",
    };

    private static string TruncateMessage(string msg) =>
        msg.Length <= 2000 ? msg : msg[..2000];
}
