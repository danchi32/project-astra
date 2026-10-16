using System;
using System.Drawing;
using System.Windows.Forms;
using AstraAgent.Service.Security;
using AstraAgent.Service.Workforce;
using AstraAgent.Tray.Remediation;
using AstraAgent.Tray.Update;
using Microsoft.Extensions.Configuration;

namespace AstraAgent.Tray;

/// <summary>Owns the tray icon for the ASTRA assistant and opens the chat popup on click.</summary>
public sealed class TrayApplicationContext : ApplicationContext
{
    private readonly NotifyIcon _icon;
    private readonly TrayChatClient _client;
    private readonly RemediationRunner _runner;
    private readonly TrayUpdater _updater;
    private readonly Icon _brandIcon = LoadBrandIcon();
    private ChatForm? _chatForm;

    // Transparency for Workforce Insights ("Tracker"): when the org is being tracked, the
    // person sees it here — no covert mode. The Service writes the flag to the registry on
    // every beat; the Tray polls it and reflects it. A disabled menu line and the tooltip
    // say so; the item is hidden entirely when tracking is off.
    private const string TrackingOnText = "● Activity tracking: ON";
    private readonly ToolStripSeparator _trackingSeparator = new() { Visible = false };
    private readonly ToolStripMenuItem _trackingItem = new(TrackingOnText)
    {
        Enabled = false,
        Visible = false,
        ToolTipText =
            "Your organisation has activity tracking enabled. Work hours (sign-in, sign-out "
            + "and active time) are recorded. No keystrokes, screenshots or screen recording.",
    };
    private readonly System.Windows.Forms.Timer _trackingTimer = new() { Interval = 60_000 };
    private bool _trackingOn;

    /// <summary>The Technomate brand mark, embedded in this assembly. Falls back to a system
    /// icon if the resource is somehow missing, so the tray never fails to appear.</summary>
    private static Icon LoadBrandIcon()
    {
        try
        {
            var stream = typeof(TrayApplicationContext).Assembly
                .GetManifestResourceStream("AstraAgent.Tray.astra.ico");
            if (stream is not null)
                return new Icon(stream);
        }
        catch { /* fall through */ }
        return SystemIcons.Information;
    }

    public TrayApplicationContext()
    {
        var config = new ConfigurationBuilder()
            .SetBasePath(AppContext.BaseDirectory)
            .AddJsonFile("appsettings.json", optional: true)
            .AddEnvironmentVariables()
            .Build();
        var serverUrl = config["Astra:ServerUrl"] ?? "http://localhost:8000";
        // Same corporate-proxy handling as the service, so the tray's chat/remediation/update
        // traffic also traverses a proxied network. Empty by default (auto-detect).
        var proxyUrl = config["Astra:ProxyUrl"];

        var tokenStore = new DpapiTokenStore();
        _client = new TrayChatClient(serverUrl, tokenStore, proxyUrl);

        // Execute approved remediation tasks in the background while the assistant runs.
        _runner = new RemediationRunner(serverUrl, tokenStore, proxyUrl);
        _runner.Start();

        // Keep the tray up to date in the background (no-op unless it's running from its live
        // copy and a signing key is pinned).
        _updater = new TrayUpdater(serverUrl, tokenStore, proxyUrl);
        _updater.Start();

        var menu = new ContextMenuStrip();
        menu.Items.Add("Open ASTRA Assistant", null, (_, _) => ShowChat());
        menu.Items.Add(_trackingItem);
        menu.Items.Add(_trackingSeparator);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Exit", null, (_, _) => ExitThread());

        _icon = new NotifyIcon
        {
            Icon = _brandIcon,
            Text = "ASTRA Assistant — click for help",
            Visible = true,
            ContextMenuStrip = menu,
        };
        _icon.MouseClick += (_, e) =>
        {
            if (e.Button == MouseButtons.Left)
                ShowChat();
        };

        // Reflect the tracking flag now and keep it current. Polled rather than pushed: the
        // Service owns the flag and writes it to the registry, and a minute's lag on a
        // transparency indicator is immaterial.
        RefreshTrackingStatus();
        _trackingTimer.Tick += (_, _) => RefreshTrackingStatus();
        _trackingTimer.Start();

        // Tell the user where the icon lives; clicking it opens the chat.
        _icon.ShowBalloonTip(
            5000, "ASTRA Assistant",
            "ASTRA is running. Click this icon whenever you need help. "
            + "(If you don't see the icon, click the ^ arrow near the clock.)",
            ToolTipIcon.Info);
    }

    /// <summary>Read the tracking flag the Service last wrote and show or hide the indicator.
    /// On the transition OFF→ON, a one-time balloon makes sure the person is actually told,
    /// not just shown a menu line they might never open.</summary>
    private void RefreshTrackingStatus()
    {
        bool on;
        try { on = ActivityTrackingState.ReadFromRegistry(); }
        catch { on = false; }   // never let a status read crash the tray

        if (on == _trackingOn)
            return;
        _trackingOn = on;

        _trackingItem.Visible = on;
        _trackingSeparator.Visible = on;
        _icon.Text = on
            ? "ASTRA — activity tracking is on"   // NotifyIcon.Text caps at 63 chars
            : "ASTRA Assistant — click for help";

        if (on)
            _icon.ShowBalloonTip(
                7000, "Activity tracking is on",
                "Your organisation records work hours (sign-in, sign-out and active time) "
                + "through ASTRA. No keystrokes, screenshots or screen recording.",
                ToolTipIcon.Info);
    }

    private void ShowChat()
    {
        if (_chatForm is null || _chatForm.IsDisposed)
        {
            _chatForm = new ChatForm(_client) { Icon = _brandIcon };
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
            _trackingTimer.Dispose();
            _updater.Dispose();
            _runner.Dispose();
            _icon.Visible = false;
            _icon.Dispose();
            _chatForm?.Dispose();
            _brandIcon.Dispose();
        }
        base.Dispose(disposing);
    }
}
