using System.ServiceProcess;

namespace AstraAgent.Service.Telemetry.Collectors;

public sealed class ServicesCollector(ILogger<ServicesCollector> logger) : IServicesCollector
{
    public IReadOnlyList<WindowsService> GetServices()
    {
        try
        {
            return ServiceController
                .GetServices()
                .Select(s =>
                {
                    using (s)
                    {
                        return new WindowsService(
                            s.ServiceName,
                            s.DisplayName,
                            s.Status.ToString(),
                            s.StartType.ToString());
                    }
                })
                .OrderBy(s => s.DisplayName)
                .ToList();
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Services collection failed");
            return [];
        }
    }
}
