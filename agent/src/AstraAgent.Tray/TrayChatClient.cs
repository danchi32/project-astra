using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using AstraAgent.Service.Security;

namespace AstraAgent.Tray;

/// <summary>Talks to the backend's device-authenticated chat endpoint using the
/// device token the service stored via DPAPI — no user login required.</summary>
public sealed class TrayChatClient
{
    private readonly HttpClient _http;
    private readonly ITokenStore _store;
    private readonly string _statePath;
    private Guid? _conversationId;

    public TrayChatClient(string serverUrl, ITokenStore store, string? proxyUrl = null)
    {
        _http = new HttpClient(AstraAgent.Service.Net.ProxyHttp.CreateHandler(proxyUrl))
        {
            BaseAddress = new Uri(serverUrl),
            Timeout = TimeSpan.FromSeconds(90),
        };
        _store = store;

        // Remember which conversation we're in across window opens AND tray restarts,
        // so the chat continues instead of starting fresh every time.
        var dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Astra");
        _statePath = Path.Combine(dir, "conversation.txt");
        try
        {
            if (File.Exists(_statePath) && Guid.TryParse(File.ReadAllText(_statePath).Trim(), out var id))
                _conversationId = id;
        }
        catch { /* first run / unreadable — start fresh */ }
    }

    public bool IsEnrolled => _store.Load() is not null;

    private void PersistConversationId()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_statePath)!);
            File.WriteAllText(_statePath, _conversationId?.ToString() ?? string.Empty);
        }
        catch { /* best-effort persistence */ }
    }

    /// <summary>Fetch the device's most recent conversation so the chat window can restore
    /// what was said before. Returns (role, content) pairs oldest-first.</summary>
    public async Task<IReadOnlyList<(string Role, string Content)>> LoadHistoryAsync(CancellationToken ct)
    {
        var token = _store.Load();
        if (token is null)
            return Array.Empty<(string, string)>();

        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, "/api/v1/agent/conversation");
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var response = await _http.SendAsync(request, ct);
            if (!response.IsSuccessStatusCode)
                return Array.Empty<(string, string)>();

            var body = await response.Content.ReadFromJsonAsync<HistoryResponse>(ct);
            if (body?.ConversationId is Guid cid)
            {
                _conversationId = cid;
                PersistConversationId();
            }
            var list = new List<(string, string)>();
            foreach (var m in body?.Messages ?? new List<HistoryMessage>())
                list.Add((m.Role, m.Content));
            return list;
        }
        catch
        {
            return Array.Empty<(string, string)>();
        }
    }

    public async Task<string> SendAsync(string message, CancellationToken ct)
    {
        var token = _store.Load();
        if (token is null)
            return "This device isn't enrolled with ASTRA yet. Please contact your IT administrator.";

        var response = await PostChatAsync(token, message, ct);

        // A 404 means our cached conversation no longer exists (e.g. the server was reset).
        // Drop it and start a fresh conversation, then retry once.
        if (response.StatusCode == HttpStatusCode.NotFound && _conversationId is not null)
        {
            response.Dispose();
            _conversationId = null;
            PersistConversationId();
            response = await PostChatAsync(token, message, ct);
        }

        using (response)
        {
            if (!response.IsSuccessStatusCode)
                return $"Sorry, I couldn't reach ASTRA right now (error {(int)response.StatusCode}). "
                     + "Please try again in a moment.";

            var body = await response.Content.ReadFromJsonAsync<ChatResponse>(ct);
            if (body is null)
                return "Sorry, I received an empty response from ASTRA.";

            _conversationId = body.ConversationId;
            PersistConversationId();
            return body.Reply;
        }
    }

    private async Task<HttpResponseMessage> PostChatAsync(
        string token, string message, CancellationToken ct)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agent/chat")
        {
            Content = JsonContent.Create(new ChatRequest(message, _conversationId)),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        return await _http.SendAsync(request, ct);
    }

    private sealed record ChatRequest(
        [property: JsonPropertyName("content")] string Content,
        [property: JsonPropertyName("conversation_id")] Guid? ConversationId);

    private sealed record ChatResponse(
        [property: JsonPropertyName("conversation_id")] Guid ConversationId,
        [property: JsonPropertyName("reply")] string Reply);

    private sealed record HistoryResponse(
        [property: JsonPropertyName("conversation_id")] Guid? ConversationId,
        [property: JsonPropertyName("messages")] List<HistoryMessage> Messages);

    private sealed record HistoryMessage(
        [property: JsonPropertyName("role")] string Role,
        [property: JsonPropertyName("content")] string Content);
}
