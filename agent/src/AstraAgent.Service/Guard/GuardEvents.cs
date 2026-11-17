using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using AstraAgent.Guard;
using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;

namespace AstraAgent.Service.Guard;

/// <summary>An event as the service holds it: what the extension saw, when, and the Windows
/// account that was signed in, as Windows reported it.</summary>
public sealed record QueuedGuardEvent(DateTime At, string WindowsUser, GuardEvent Event);

/// <summary>
/// Phase 3 · E3: events waiting to go to the backend.
///
/// Kept on disk as well as in memory (<c>state\guard-events.jsonl</c>, SYSTEM and
/// Administrators only), so a restart or a reboot on a laptop that has been offline does not
/// lose them. Appended as they come, rewritten when the backend has taken a batch, read back
/// (and checked line by line) on start. If the folder cannot be locked down or the file cannot
/// be written, the queue carries on in memory.
///
/// Bounded twice. At most <see cref="Capacity"/> are held; past that the newest are dropped,
/// so a long offline spell keeps its first hours rather than its last. At most
/// <see cref="PerMinute"/> are taken in any minute, so a page or a person cannot flood it.
/// Drops are counted and logged by the uploader.
/// </summary>
public sealed class GuardEventQueue
{
    public const int Capacity = 5000;
    public const int PerMinute = 120;

    readonly object _gate = new();
    readonly List<QueuedGuardEvent> _items = [];
    readonly string? _file;
    DateTime _window = DateTime.MinValue;
    int _inWindow;

    /// <param name="file">Where to keep the queue; null for memory only (tests).</param>
    public GuardEventQueue(string? file = null)
    {
        _file = file;
        if (_file is null) return;
        try
        {
            if (!File.Exists(_file)) return;
            foreach (var line in File.ReadLines(_file))
            {
                if (_items.Count >= Capacity) break;
                if (Parse(line) is { } e) _items.Add(e);   // a torn or edited line is skipped, not fatal
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { }
    }

    /// <summary>The real queue, in the hardened state folder. Memory only if that folder cannot be secured.</summary>
    public static GuardEventQueue OnDisk()
    {
        var dir = Security.SecureDirectory.StateRoot;
        try
        {
            Security.SecureDirectory.Ensure(dir);
            var file = Path.Combine(dir, "guard-events.jsonl");
            Security.SecureDirectory.EnsureFile(file);
            return new GuardEventQueue(file);
        }
        catch (Exception) { return new GuardEventQueue(); }
    }

    public int Dropped { get; private set; }

    public int Count { get { lock (_gate) return _items.Count; } }

    public bool TryAdd(QueuedGuardEvent e)
    {
        lock (_gate)
        {
            var minute = new DateTime(e.At.Ticks - e.At.Ticks % TimeSpan.TicksPerMinute, DateTimeKind.Utc);
            if (minute != _window) (_window, _inWindow) = (minute, 0);
            if (_inWindow >= PerMinute || _items.Count >= Capacity) { Dropped++; return false; }
            _inWindow++;
            _items.Add(e);
            Persist(() => File.AppendAllText(_file!, Line(e) + "\n"));
            return true;
        }
    }

    public IReadOnlyList<QueuedGuardEvent> Peek(int max)
    {
        lock (_gate) return _items.Take(max).ToList();
    }

    /// <summary>Forget the first <paramref name="count"/> events, once the backend has them.</summary>
    public void Remove(int count)
    {
        lock (_gate)
        {
            _items.RemoveRange(0, Math.Min(count, _items.Count));
            Persist(() =>
            {
                var tmp = _file + ".tmp";
                File.WriteAllLines(tmp, _items.Select(Line));
                File.Move(tmp, _file!, overwrite: true);
            });
        }
    }

    void Persist(Action write)
    {
        if (_file is null) return;
        try { write(); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { }
    }

    sealed record Stored(DateTime At, string WindowsUser, GuardEvent Event);

    static string Line(QueuedGuardEvent e) =>
        System.Text.Json.JsonSerializer.Serialize(new Stored(e.At, e.WindowsUser, e.Event), GuardEvent.Json);

    static QueuedGuardEvent? Parse(string line)
    {
        try
        {
            var s = System.Text.Json.JsonSerializer.Deserialize<Stored>(line, GuardEvent.Json);
            return s is { WindowsUser.Length: > 0 and <= 256, Event: not null } && s.Event.IsValid()
                ? new QueuedGuardEvent(DateTime.SpecifyKind(s.At, DateTimeKind.Utc), s.WindowsUser, s.Event)
                : null;
        }
        catch (System.Text.Json.JsonException) { return null; }
    }
}

/// <summary>
/// Phase 3 · E3: the local pipe the native host hands events to.
///
/// Write-only from the host's side, one event per connection, at most
/// <see cref="GuardEvent.MaxBytes"/>, read within two seconds. Anything that is not exactly a
/// <see cref="GuardEvent"/> is dropped. Who sent it is taken from Windows, not from the message.
/// The host connects at Identification level, so the service can read the account and do
/// nothing as it. A client that will not be identified is refused.
/// </summary>
public sealed class GuardEventPipeServer(GuardEventQueue queue, ILogger<GuardEventPipeServer> logger) : BackgroundService
{
    public const string PipeName = "SAVIO.GuardEvents";

    /// <summary>Tests use their own name and no ACL: only SYSTEM may create a SYSTEM-owned pipe.</summary>
    internal string Name { get; init; } = PipeName;
    /// <summary>Same rules as Fix-my-internet: owned by SYSTEM, signed-in people may connect, no network.</summary>
    internal Func<PipeSecurity?> Security { get; init; } = Workers.NetworkFixPipeServer.Security;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await using var pipe = Create();
                await pipe.WaitForConnectionAsync(stoppingToken);
                await HandleAsync(pipe, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { return; }
            catch (Exception ex)
            {
                logger.LogWarning(ex, "Guard event pipe error");
                try { await Task.Delay(1000, stoppingToken); } catch (OperationCanceledException) { return; }
            }
        }
    }

    internal NamedPipeServerStream Create()
    {
        // FirstPipeInstance: if anyone else already created this name, fail rather than share it.
        var options = PipeOptions.Asynchronous | PipeOptions.FirstPipeInstance;
        var security = Security();
        return security is null
            ? new NamedPipeServerStream(Name, PipeDirection.In, 1, PipeTransmissionMode.Byte, options, GuardEvent.MaxBytes, 0)
            : NamedPipeServerStreamAcl.Create(Name, PipeDirection.In, 1, PipeTransmissionMode.Byte, options,
                                              GuardEvent.MaxBytes, 0, security);
    }

    internal async Task<bool> HandleAsync(NamedPipeServerStream pipe, CancellationToken ct)
    {
        string? user = null;
        try { pipe.RunAsClient(() => user = WindowsIdentity.GetCurrent(ifImpersonating: true)?.Name); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Security.SecurityException) { }
        if (string.IsNullOrEmpty(user) || user.Length > 256)
            return false;   // not identified: the event cannot be attributed, so it is not taken

        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct);
        timeout.CancelAfter(TimeSpan.FromSeconds(2));
        var buf = new byte[GuardEvent.MaxBytes + 1];
        int read = 0, n;
        try
        {
            while (read < buf.Length && (n = await pipe.ReadAsync(buf.AsMemory(read), timeout.Token)) > 0)
                read += n;
        }
        catch (OperationCanceledException) when (!ct.IsCancellationRequested) { return false; }

        var e = read <= GuardEvent.MaxBytes ? GuardEvent.Parse(buf.AsSpan(0, read)) : null;
        if (e is null || !e.Notable)
            return false;
        return queue.TryAdd(new QueuedGuardEvent(DateTime.UtcNow, user, e));
    }
}

/// <summary>Phase 3 · E3: sends queued events to the backend, up to 500 a minute.</summary>
public sealed class GuardEventUploader(
    GuardEventQueue queue,
    IEnrollmentService enrollment,
    IAstraApiClient api,
    SubscriptionState subscription,
    ILogger<GuardEventUploader> logger) : BackgroundService
{
    internal const int BatchSize = 500;
    int _droppedReported;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try { await RunOnceAsync(stoppingToken); }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
            catch (Exception ex) { logger.LogError(ex, "Guard event upload failed"); }
            try { await Task.Delay(TimeSpan.FromMinutes(1), stoppingToken); }
            catch (OperationCanceledException) { break; }
        }
    }

    internal async Task RunOnceAsync(CancellationToken ct)
    {
        if (subscription.Dormant) return;
        var batch = queue.Peek(BatchSize);
        if (batch.Count == 0) return;
        var token = await enrollment.GetDeviceTokenAsync(ct);
        if (token is null) return;
        if (await api.SendGuardEventsAsync(token, batch, ct))
            queue.Remove(batch.Count);
        if (queue.Dropped > _droppedReported)
        {
            logger.LogWarning("{Count} browser guard events were dropped (rate or queue limit)", queue.Dropped - _droppedReported);
            _droppedReported = queue.Dropped;
        }
    }
}
