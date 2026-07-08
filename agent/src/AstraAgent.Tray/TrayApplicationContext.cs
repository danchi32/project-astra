using System;
using System.Drawing;
using System.Windows.Forms;
using AstraAgent.Service.Security;
using Microsoft.Extensions.Configuration;

namespace AstraAgent.Tray;

/// <summary>Owns the tray icon for the ASTRA assistant and opens the chat popup on click.</summary>
public sealed class TrayApplicationContext : ApplicationContext
{
    private readonly NotifyIcon _icon;
    private readonly TrayChatClient _client;
    private ChatForm? _chatForm;

    public TrayApplicationContext()
    {
        var config = new ConfigurationBuilder()
            .SetBasePath(AppContext.BaseDirectory)
            .AddJsonFile("appsettings.json", optional: true)
            .AddEnvironmentVariables()
            .Build();
        var serverUrl = config["Astra:ServerUrl"] ?? "http://localhost:8000";

        _client = new TrayChatClient(serverUrl, new DpapiTokenStore());

        var menu = new ContextMenuStrip();
        menu.Items.Add("Open ASTRA Assistant", null, (_, _) => ShowChat());
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Exit", null, (_, _) => ExitThread());

        _icon = new NotifyIcon
        {
            Icon = SystemIcons.Information,
            Text = "ASTRA Assistant — click for help",
            Visible = true,
            ContextMenuStrip = menu,
        };
        _icon.MouseClick += (_, e) =>
        {
            if (e.Button == MouseButtons.Left)
                ShowChat();
        };

        // Tell the user where the icon lives; clicking it opens the chat.
        _icon.ShowBalloonTip(
            5000, "ASTRA Assistant",
            "ASTRA is running. Click this icon whenever you need help. "
            + "(If you don't see the icon, click the ^ arrow near the clock.)",
            ToolTipIcon.Info);
    }

    private void ShowChat()
    {
        if (_chatForm is null || _chatForm.IsDisposed)
        {
            _chatForm = new ChatForm(_client);
            _chatForm.HiddenToTray += (_, _) => _icon.ShowBalloonTip(
                2500, "ASTRA Assistant",
                "I'm still here — click this icon to chat again.", ToolTipIcon.Info);
        }
        _chatForm.ShowInLowerRight();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _icon.Visible = false;
            _icon.Dispose();
            _chatForm?.Dispose();
        }
        base.Dispose(disposing);
    }
}
