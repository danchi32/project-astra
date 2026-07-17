using System;
using System.Collections.Generic;
using System.Drawing;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace AstraAgent.Tray;

/// <summary>A small chat window pinned to the lower-right corner, above the taskbar.</summary>
public sealed class ChatForm : Form
{
    private readonly TrayChatClient _client;
    private readonly FlowLayoutPanel _messages;
    private readonly TextBox _input;
    private readonly Button _send;
    private bool _historyLoaded;

    // How many server-side messages we've already rendered. After the AI queues a fix,
    // the backend appends the real "✅ done" / "⚠️ couldn't" line once the agent runs it;
    // we poll and render any messages beyond this high-water mark.
    private int _serverMsgCount;
    private CancellationTokenSource? _pollCts;

    private static readonly Color BgColor = Color.FromArgb(248, 250, 252);
    private static readonly Color AccentColor = Color.FromArgb(37, 99, 235);
    private static readonly Color TextColor = Color.FromArgb(15, 23, 42);

    /// <summary>Raised when the window minimizes or is closed to the tray, so the tray
    /// icon can nudge the user on how to bring it back.</summary>
    public event EventHandler? HiddenToTray;

    public ChatForm(TrayChatClient client)
    {
        _client = client;

        Text = "ASTRA Assistant";
        // FixedSingle gives a real title bar with a minimize button (a tool window has none).
        FormBorderStyle = FormBorderStyle.FixedSingle;
        StartPosition = FormStartPosition.Manual;
        ShowInTaskbar = false;   // lives in the tray, not the taskbar
        MinimizeBox = true;
        MaximizeBox = false;
        Size = new Size(380, 520);
        BackColor = BgColor;
        Font = new Font("Segoe UI", 9F);

        // Minimizing hides the window back to the tray instead of shrinking to the taskbar.
        Resize += (_, _) =>
        {
            if (WindowState == FormWindowState.Minimized)
            {
                Hide();
                HiddenToTray?.Invoke(this, EventArgs.Empty);
            }
        };

        _messages = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false,
            AutoScroll = true,
            Padding = new Padding(8),
            BackColor = BgColor,
        };

        var composer = new Panel { Dock = DockStyle.Bottom, Height = 46, Padding = new Padding(6) };
        _send = new Button { Text = "Send", Dock = DockStyle.Right, Width = 68, FlatStyle = FlatStyle.Flat };
        _send.FlatAppearance.BorderSize = 0;
        _send.BackColor = AccentColor;
        _send.ForeColor = Color.White;
        _send.Click += async (_, _) => await SendAsync();
        _input = new TextBox { Dock = DockStyle.Fill, BorderStyle = BorderStyle.FixedSingle };
        _input.KeyDown += async (_, e) =>
        {
            if (e.KeyCode == Keys.Enter)
            {
                e.SuppressKeyPress = true;
                await SendAsync();
            }
        };
        composer.Controls.Add(_input);
        composer.Controls.Add(_send);

        Controls.Add(_messages);
        Controls.Add(composer);

        AddBubble(
            "Hi! I'm ASTRA, your IT assistant. Tell me what's going wrong with your computer "
            + "and I'll take a look.",
            fromUser: false);
    }

    public void ShowInLowerRight()
    {
        // Restore from minimized/hidden and pin to the lower-right corner above the taskbar.
        WindowState = FormWindowState.Normal;
        var area = Screen.PrimaryScreen!.WorkingArea;
        Location = new Point(area.Right - Width - 12, area.Bottom - Height - 12);
        Show();
        BringToFront();
        Activate();
        _input.Focus();

        // Restore the prior conversation the first time the window is shown.
        if (!_historyLoaded)
        {
            _historyLoaded = true;
            _ = LoadHistoryAsync();
        }
    }

    private async Task LoadHistoryAsync()
    {
        try
        {
            var history = await _client.LoadHistoryAsync(CancellationToken.None);
            if (history.Count == 0)
                return;   // keep the friendly greeting for a brand-new chat

            _messages.Controls.Clear();   // drop the placeholder greeting
            foreach (var (role, content) in history)
                AddBubble(content, fromUser: role == "user");
            _serverMsgCount = history.Count;
        }
        catch { /* leave the greeting in place if history can't be loaded */ }
    }

    // Hide on close instead of disposing, so the conversation stays visible next time.
    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if (e.CloseReason == CloseReason.UserClosing)
        {
            e.Cancel = true;
            Hide();
            HiddenToTray?.Invoke(this, EventArgs.Empty);
        }
        else
        {
            base.OnFormClosing(e);
        }
    }

    private async Task SendAsync()
    {
        var text = _input.Text.Trim();
        if (text.Length == 0)
            return;

        _input.Clear();
        AddBubble(text, fromUser: true);
        _send.Enabled = false;
        var pending = AddBubble("Investigating…", fromUser: false);

        try
        {
            var reply = await _client.SendAsync(text, CancellationToken.None);
            pending.Text = reply;
            // The turn stored two server messages (this user turn + the AI reply). Anything
            // beyond that is the execution result the backend posts once the agent runs.
            _serverMsgCount += 2;
            StartResultPolling();
        }
        catch (Exception ex)
        {
            pending.Text = "Sorry, something went wrong: " + ex.Message;
        }
        finally
        {
            _send.Enabled = true;
            _input.Focus();
            _messages.ScrollControlIntoView(pending);
        }
    }

    /// <summary>After a turn, briefly poll for messages the backend appends when the agent
    /// finishes running a queued fix, and render them as they arrive.</summary>
    private void StartResultPolling()
    {
        _pollCts?.Cancel();
        _pollCts = new CancellationTokenSource();
        var ct = _pollCts.Token;
        _ = PollForResultAsync(ct);
    }

    private async Task PollForResultAsync(CancellationToken ct)
    {
        // Poll every 3s for ~2 minutes — long enough for the agent's next remediation poll
        // and execution, short enough not to run forever.
        for (var i = 0; i < 40 && !ct.IsCancellationRequested; i++)
        {
            try
            {
                await Task.Delay(TimeSpan.FromSeconds(3), ct);
            }
            catch (TaskCanceledException)
            {
                return;
            }

            IReadOnlyList<(string Role, string Content)> history;
            try
            {
                history = await _client.LoadHistoryAsync(ct);
            }
            catch
            {
                continue;   // transient — try again next tick
            }

            if (ct.IsCancellationRequested || history.Count <= _serverMsgCount)
                continue;

            var terminal = false;
            for (var j = _serverMsgCount; j < history.Count; j++)
            {
                var (role, content) = history[j];
                AddBubble(content, fromUser: role == "user");
                if (content.StartsWith("✅") || content.StartsWith("⚠️"))
                    terminal = true;
            }
            _serverMsgCount = history.Count;

            if (terminal)
                return;   // the fix reported its outcome — stop polling
        }
    }

    private Label AddBubble(string text, bool fromUser)
    {
        var label = new Label
        {
            Text = text,
            AutoSize = true,
            MaximumSize = new Size(300, 0),
            Padding = new Padding(10, 8, 10, 8),
            Margin = new Padding(fromUser ? 48 : 4, 4, fromUser ? 4 : 48, 4),
            BackColor = fromUser ? AccentColor : Color.White,
            ForeColor = fromUser ? Color.White : TextColor,
        };
        _messages.Controls.Add(label);
        _messages.ScrollControlIntoView(label);
        return label;
    }
}
