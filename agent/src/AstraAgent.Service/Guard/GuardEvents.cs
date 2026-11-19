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
/// <see cref="PerMinute"/> are taken in any minute, and at most <see cref="PerUserPerMinute"/> from
/// any one Windows account, so one person on a shared PC cannot crowd out everyone else's events
/// (security review M2). Drops are counted and logged by the uploader.
/// </summary>
public sealed class GuardEventQueue
{
    public const int Capacity = 5000;
    public const int PerMinute = 240;
    public const int PerUserPerMinute = 60;

    readonly object _gate = new();
    readonly List<QueuedGuardEvent> _items = [];
    readonly string? _file;
    DateTime _window = DateTime.MinValue;
    int _inWindow;
    readonly Dictionary<string, int> _byUser = new(StringComparer.OrdinalIgnoreCase);

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
            if (minute != _window) { (_window, _inWindow) = (minute, 0); _byUser.Clear(); }
            var mine = _byUser.GetValueOrDefault(e.WindowsUser);
            if (_inWindow >= PerMinute || mine >= PerUserPerMinute || _items.Count >= Capacity) { Dropped++; return false; }
            _inWindow++;
            _byUser[e.WindowsUser] = mine + 1;
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

    /// <summary>Connections handled at once. While one is being read, another instance is
    /// already listening, so the name is never free for someone else to take (security review
    /// M2), and a client that connects and says nothing holds up only its own slot.</summary>
    internal const int MaxInstances = 4;
    static readonly TimeSpan ReadTimeout = TimeSpan.FromMilliseconds(500);

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var slots = new SemaphoreSlim(MaxInstances);
        var first = true;
        NamedPipeServerStream? listening = null;
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                if (listening is null)
                {
                    await slots.WaitAsync(stoppingToken);
                    try { listening = Create(first); first = false; }
                    catch { slots.Release(); throw; }
                }
                await listening.WaitForConnectionAsync(stoppingToken);
                var connected = listening;
                listening = null;   // the next pass opens the next instance straight away
                _ = Task.Run(async () =>
                {
                    try { await HandleAsync(connected, stoppingToken); }
                    catch (Exception ex) when (ex is not OperationCanceledException) { logger.LogDebug(ex, "Guard event not read"); }
                    finally { await connected.DisposeAsync(); slots.Release(); }
                }, CancellationToken.None);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { return; }
            catch (Exception ex)
            {
                if (listening is not null) { await listening.DisposeAsync(); listening = null; slots.Release(); }
                first = true;   // nothing of ours is open now: the next instance must be the first again
                logger.LogWarning(ex, "Guard event pipe error");
                try { await Task.Delay(1000, stoppingToken); } catch (OperationCanceledException) { return; }
            }
        }
    }

    internal NamedPipeServerStream Create(bool first = true)
    {
        // FirstPipeInstance on the first one: if anyone else already created this name, fail
        // rather than share it. Later instances join the pipe this service already owns.
        var options = PipeOptions.Asynchronous | (first ? PipeOptions.FirstPipeInstance : PipeOptions.None);
        var security = Security();
        return security is null
            ? new NamedPipeServerStream(Name, PipeDirection.InOut, MaxInstances, PipeTransmissionMode.Byte, options, GuardEvent.MaxBytes, 1)
            : NamedPipeServerStreamAcl.Create(Name, PipeDirection.InOut, MaxInstances, PipeTransmissionMode.Byte, options,
                                              GuardEvent.MaxBytes, 1, security);
    }

    /// <summary>
    /// The Windows account of the process on the other end. Windows names the client process
    /// (GetNamedPipeClientProcessId comes from the kernel, not from anything the client says),
    /// and the service reads that process's own token. This replaced impersonating the client,
    /// which failed on a real PC: a LocalSystem service could not open an Identification-level
    /// token of another account (found in the live test; the unit tests ran as one account).
    /// The host stays connected while it waits for the answer, so its process is still there.
    /// </summary>
    internal static string? ClientAccount(NamedPipeServerStream pipe)
    {
        if (!GetNamedPipeClientProcessId(pipe.SafePipeHandle, out var pid)) return null;
        var process = OpenProcess(ProcessQueryLimitedInformation, false, pid);
        if (process == IntPtr.Zero) return null;
        try
        {
            if (!OpenProcessToken(process, TokenQuery | TokenDuplicate, out var token)) return null;
            try { using var id = new WindowsIdentity(token); return id.Name; }
            finally { CloseHandle(token); }
        }
        catch (Exception ex) when (ex is ArgumentException or System.Security.SecurityException or UnauthorizedAccessException) { return null; }
        finally { CloseHandle(process); }
    }

    const uint ProcessQueryLimitedInformation = 0x1000;
    const uint TokenQuery = 0x0008, TokenDuplicate = 0x0002;

    [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetNamedPipeClientProcessId(Microsoft.Win32.SafeHandles.SafePipeHandle pipe, out uint processId);
    [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr OpenProcess(uint access, bool inherit, uint processId);
    [System.Runtime.InteropServices.DllImport("advapi32.dll", SetLastError = true)]
    static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr handle);

    /// <summary>
    /// One event: a 4-byte length, the event, then a one-byte answer (1 taken, 0 not).
    /// The client is identified after its message is read and while it waits for the answer:
    /// Windows lets a server identify a pipe client of another account only once it has read
    /// from the pipe, and only while the client is connected. (Found in the live test on a real
    /// PC; identifying first worked only when server and client were the same account.)
    /// </summary>
    internal async Task<bool> HandleAsync(NamedPipeServerStream pipe, CancellationToken ct)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct);
        timeout.CancelAfter(ReadTimeout);
        byte[] body;
        try
        {
            var head = new byte[4];
            await pipe.ReadExactlyAsync(head, timeout.Token);
            var length = BitConverter.ToInt32(head);
            if (length is <= 0 or > GuardEvent.MaxBytes) return false;
            body = new byte[length];
            await pipe.ReadExactlyAsync(body, timeout.Token);
        }
        catch (Exception ex) when (ex is OperationCanceledException or EndOfStreamException or IOException
                                       && !ct.IsCancellationRequested) { return false; }

        var user = ClientAccount(pipe);
        var e = GuardEvent.Parse(body);
        var taken = !string.IsNullOrEmpty(user) && user.Length <= 256   // not identified: cannot be attributed
                    && e is not null && e.Notable
                    && e.Channel != "usb"   // C3b: only the service itself records USB copies
                    && queue.TryAdd(new QueuedGuardEvent(DateTime.UtcNow, user, e));
        try
        {
            await pipe.WriteAsync(new[] { (byte)(taken ? 1 : 0) }, timeout.Token);
            await pipe.FlushAsync(timeout.Token);
        }
        catch (Exception ex) when (ex is OperationCanceledException or IOException) { }
        return taken;
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
