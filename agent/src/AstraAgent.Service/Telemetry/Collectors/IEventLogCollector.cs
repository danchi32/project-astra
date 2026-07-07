namespace AstraAgent.Service.Telemetry.Collectors;

public sealed record EventLogEntry(
    string LogName,
    string Source,
    int EventId,
    string Level,
    string Message,
    DateTimeOffset OccurredAt);

public interface IEventLogCollector
{
    IReadOnlyList<EventLogEntry> GetRecentEntries(int maxEntries = 50);
}
