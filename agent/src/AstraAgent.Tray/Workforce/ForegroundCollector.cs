using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using AstraAgent.Service.Security;
using AstraAgent.Service.Workforce;

namespace AstraAgent.Tray.Workforce;

/// <summary>Samples the foreground app/website on a timer and ships the samples to the backend
/// as Workforce Insights activity — the Tray's half of productivity tracking.
///
/// Gated on the same flag the Tray's "Activity tracking: ON" indicator reads: nothing is
/// sampled or sent unless the backend has turned tracking on for this org. Sampling, not
/// timing — each sample stands for one interval of time in that app, which is what the backend
/// attributes; a missed flush just resends buffered samples next time.</summary>
public sealed class ForegroundCollector : IDisposable
{
    // Must match the backend's workforce_foreground_sample_seconds (30s): the backend counts
    // each sample as this much time, so a different cadence would mis-measure productivity.
    private static readonly TimeSpan SampleInterval = TimeSpan.FromSeconds(30);
    // Flush roughly every few minutes rather than every sample, to keep this off the per-30s
    // request path — a handful of samples per POST.
    private const int FlushEverySamples = 6;
    // Don't let the buffer grow without bound while the backend is unreachable.
    private const int MaxBuffer = 240;

    private readonly HttpClient _http;
    private readonly ITokenStore _store;
    private readonly List<ActivityDto> _buffer = new();
    private readonly CancellationTokenSource _cts = new();
    private readonly string _username = $"{Environment.UserDomainName}\\{Environment.UserName}";
    private Task? _loop;

    public ForegroundCollector(string serverUrl, ITokenStore store, string? proxyUrl = null)
    {
        _http = new HttpClient(AstraAgent.Service.Net.ProxyHttp.CreateHandler(proxyUrl))
        {
            BaseAddress = new Uri(serverUrl), Timeout = TimeSpan.FromSeconds(30),
        };
        _store = store;
    }

    public void Start() => _loop = Task.Run(() => LoopAsync(_cts.Token));

    private async Task LoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try { TickOnce(); }
            catch { /* a bad sample must never stop the loop */ }

            if (_buffer.Count >= FlushEverySamples)
            {
                try { await FlushAsync(ct); }
                catch (OperationCanceledException) { break; }
                catch { /* keep the buffer and retry next tick */ }
            }

            try { await Task.Delay(SampleInterval, ct); }
            catch (OperationCanceledException) { break; }
        }

        // One last flush on the way out, so the final few minutes aren't lost on logoff.
        try { await FlushAsync(CancellationToken.None); } catch { /* best-effort */ }
    }

    private void TickOnce()
    {
        // Self-gating: only collect while the backend has tracking on for this org. Reading
        // the flag the Service wrote keeps the Tray from ever collecting covertly.
        if (!ActivityTrackingState.ReadFromRegistry())
        {
            _buffer.Clear();   // tracking was turned off — drop anything not yet sent
            return;
        }

        var sample = ForegroundSampler.Capture(ActivityTrackingState.ReadUrlModeFromRegistry());
        if (sample is null)
            return;

        _buffer.Add(new ActivityDto(
            _username, "foreground", DateTimeOffset.UtcNow, sample.App, sample.Domain, sample.Path));
        if (_buffer.Count > MaxBuffer)
            _buffer.RemoveRange(0, _buffer.Count - MaxBuffer);
    }

    private async Task FlushAsync(CancellationToken ct)
    {
        if (_buffer.Count == 0)
            return;
        var token = _store.Load();
        if (token is null)
            return;   // not enrolled yet — keep buffering

        var batch = _buffer.ToArray();
        using var request = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/activity")
        {
            Content = JsonContent.Create(new ActivityPushDto(batch)),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        using var response = await _http.SendAsync(request, ct);
        if (response.IsSuccessStatusCode)
            _buffer.RemoveRange(0, Math.Min(batch.Length, _buffer.Count));
        // On failure the buffer is left intact and retried next tick.
    }

    public void Dispose()
    {
        _cts.Cancel();
        try { _loop?.Wait(TimeSpan.FromSeconds(2)); }
        catch { /* ignore shutdown races */ }
        _cts.Dispose();
        _http.Dispose();
    }

    private sealed record ActivityDto(
        [property: JsonPropertyName("username")] string Username,
        [property: JsonPropertyName("kind")] string Kind,
        [property: JsonPropertyName("occurred_at")] DateTimeOffset OccurredAt,
        [property: JsonPropertyName("app")] string? App,
        [property: JsonPropertyName("domain")] string? Domain,
        [property: JsonPropertyName("path")] string? Path);

    private sealed record ActivityPushDto(
        [property: JsonPropertyName("activity")] IReadOnlyList<ActivityDto> Activity);
}
