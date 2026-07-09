using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using AstraAgent.Service.Security;

namespace AstraAgent.Tray.Remediation;

/// <summary>Background loop that claims approved remediation tasks for this device and
/// executes them via the allowlisted RemediationExecutor, reporting each result.</summary>
public sealed class RemediationRunner : IDisposable
{
    private static readonly TimeSpan PollInterval = TimeSpan.FromSeconds(10);

    private readonly HttpClient _http;
    private readonly ITokenStore _store;
    private readonly RemediationExecutor _executor = new();
    private readonly CancellationTokenSource _cts = new();
    private Task? _loop;

    public RemediationRunner(string serverUrl, ITokenStore store)
    {
        _http = new HttpClient { BaseAddress = new Uri(serverUrl), Timeout = TimeSpan.FromSeconds(60) };
        _store = store;
    }

    public void Start() => _loop = Task.Run(() => LoopAsync(_cts.Token));

    private async Task LoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try { await PollOnceAsync(ct); }
            catch (OperationCanceledException) { break; }
            catch { /* transient — try again next tick */ }

            try { await Task.Delay(PollInterval, ct); }
            catch (OperationCanceledException) { break; }
        }
    }

    private async Task PollOnceAsync(CancellationToken ct)
    {
        var token = _store.Load();
        if (token is null)
            return;

        List<AgentTask>? tasks;
        using (var request = new HttpRequestMessage(HttpMethod.Get, "/api/v1/agent/tasks"))
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var response = await _http.SendAsync(request, ct);
            if (!response.IsSuccessStatusCode)
                return;
            tasks = await response.Content.ReadFromJsonAsync<List<AgentTask>>(ct);
        }
        if (tasks is null || tasks.Count == 0)
            return;

        foreach (var task in tasks)
        {
            var (success, output) = await _executor.ExecuteAsync(task.ActionId, ct);
            using var report = new HttpRequestMessage(
                HttpMethod.Post, $"/api/v1/agent/tasks/{task.Id}/result")
            {
                Content = JsonContent.Create(new ResultBody(success, output)),
            };
            report.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var _ = await _http.SendAsync(report, ct);
        }
    }

    public void Dispose()
    {
        _cts.Cancel();
        try { _loop?.Wait(TimeSpan.FromSeconds(2)); }
        catch { /* ignore shutdown races */ }
        _cts.Dispose();
        _http.Dispose();
    }

    private sealed record AgentTask(
        [property: JsonPropertyName("id")] Guid Id,
        [property: JsonPropertyName("action_id")] string ActionId);

    private sealed record ResultBody(
        [property: JsonPropertyName("success")] bool Success,
        [property: JsonPropertyName("output")] string Output);
}
