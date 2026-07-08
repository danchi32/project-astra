using System;
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

    private static readonly Color BgColor = Color.FromArgb(248, 250, 252);
    private static readonly Color AccentColor = Color.FromArgb(37, 99, 235);
    private static readonly Color TextColor = Color.FromArgb(15, 23, 42);

    public ChatForm(TrayChatClient client)
    {
        _client = client;

        Text = "ASTRA Assistant";
        FormBorderStyle = FormBorderStyle.FixedToolWindow;
        StartPosition = FormStartPosition.Manual;
        ShowInTaskbar = false;
        Size = new Size(380, 520);
        MinimumSize = new Size(320, 400);
        BackColor = BgColor;
        Font = new Font("Segoe UI", 9F);

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
        var area = Screen.PrimaryScreen!.WorkingArea;
        Location = new Point(area.Right - Width - 12, area.Bottom - Height - 12);
        Show();
        Activate();
        _input.Focus();
    }

    // Hide on close instead of disposing, so the conversation stays visible next time.
    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if (e.CloseReason == CloseReason.UserClosing)
        {
            e.Cancel = true;
            Hide();
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
