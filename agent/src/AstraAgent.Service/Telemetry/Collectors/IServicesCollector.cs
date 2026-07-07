namespace AstraAgent.Service.Telemetry.Collectors;

public sealed record WindowsService(string Name, string DisplayName, string Status, string StartType);

public interface IServicesCollector
{
    IReadOnlyList<WindowsService> GetServices();
}
