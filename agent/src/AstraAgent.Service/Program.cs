using AstraAgent.Service;
using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using AstraAgent.Service.Security;
using AstraAgent.Service.Telemetry.Collectors;
using AstraAgent.Service.Workers;
using Microsoft.Extensions.Options;

var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddWindowsService(options => options.ServiceName = "AstraAgent");

builder.Services.Configure<AgentOptions>(builder.Configuration.GetSection(AgentOptions.SectionName));
builder.Services.AddSingleton<ITokenStore, DpapiTokenStore>();
builder.Services.AddSingleton<IDeviceIdentityProvider, WindowsDeviceIdentityProvider>();
builder.Services.AddSingleton<IEnrollmentService, EnrollmentService>();

builder.Services.AddHttpClient<IAstraApiClient, AstraApiClient>((provider, http) =>
{
    var options = provider.GetRequiredService<IOptions<AgentOptions>>().Value;
    if (string.IsNullOrWhiteSpace(options.ServerUrl))
        throw new InvalidOperationException("Astra:ServerUrl is not configured");
    http.BaseAddress = new Uri(options.ServerUrl);
    http.Timeout = TimeSpan.FromSeconds(30);
});

builder.Services.AddSingleton<ICpuCollector, CpuCollector>();
builder.Services.AddSingleton<IMemoryCollector, MemoryCollector>();
builder.Services.AddSingleton<IDiskCollector, DiskCollector>();
builder.Services.AddSingleton<IEventLogCollector, EventLogCollector>();
builder.Services.AddSingleton<IInstalledAppsCollector, InstalledAppsCollector>();
builder.Services.AddSingleton<IServicesCollector, ServicesCollector>();
builder.Services.AddSingleton<IWindowsUpdateCollector, WindowsUpdateCollector>();
builder.Services.AddSingleton<IHardwareCollector, HardwareCollector>();

builder.Services.AddHostedService<HeartbeatWorker>();
builder.Services.AddHostedService<TelemetryWorker>();

builder.Build().Run();
