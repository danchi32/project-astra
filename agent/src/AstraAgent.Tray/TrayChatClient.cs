using System;
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
    private Guid? _conversationId;

    public TrayChatClient(string serverUrl, ITokenStore store)
    {
        _http = new HttpClient
        {
            BaseAddress = new Uri(serverUrl),
            Timeout = TimeSpan.FromSeconds(90),
        };
        _store = store;
    }

    public bool IsEnrolled => _store.Load() is not null;

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
}
