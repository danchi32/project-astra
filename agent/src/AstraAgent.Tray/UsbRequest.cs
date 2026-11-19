using System;
using System.Drawing;
using System.IO.Pipes;
using System.Linq;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace AstraAgent.Tray;

/// <summary>C3b: the Tray side of "Ask IT to allow USB writing". Talks only to SAVIO's own
/// service on this PC, over a local pipe that takes two fixed requests.</summary>
public static class UsbRequest
{
    // Mirrors UsbRequestPipeServer.PipeName / Reasons in the service.
    private const string PipeName = "SAVIO.UsbRequest";

    /// <summary>Why the person needs it: a fixed list, never typed text.</summary>
    public static readonly (string Code, string Label)[] Reasons =
    [
        ("client_or_ca", "Files for a client, CA or auditor"),
        ("backup", "A company backup"),
        ("presentation", "A presentation or meeting"),
        ("other", "Another work reason"),
    ];

    /// <summary>"off", "closed", "open:&lt;UTC end&gt;", or null if the service did not answer.</summary>
    public static Task<string?> StatusAsync() => AskAsync("status", TimeSpan.FromSeconds(2));

    public static async Task<string> RequestAsync(string reason) =>
        await AskAsync("request:" + reason, TimeSpan.FromSeconds(20))
        ?? "SAVIO's background service didn't answer. Restart the PC, or contact IT.";

    private static async Task<string?> AskAsync(string message, TimeSpan wait)
    {
        try
        {
            using var cts = new CancellationTokenSource(wait);
            // Identification: the service learns who we are from Windows, and can never act as us.
            await using var pipe = new NamedPipeClientStream(".", PipeName, PipeDirection.InOut,
                PipeOptions.Asynchronous, TokenImpersonationLevel.Identification);
            await pipe.ConnectAsync(cts.Token);
            if (!OwnedBySystem(pipe))
                return null;   // something other than SAVIO answered
            await pipe.WriteAsync(Encoding.UTF8.GetBytes(message), cts.Token);
            await pipe.FlushAsync(cts.Token);
            var buf = new byte[1024];
            var n = await pipe.ReadAsync(buf, cts.Token);
            return Encoding.UTF8.GetString(buf, 0, n).Trim();
        }
        catch (Exception)
        {
            return null;
        }
    }

    private static bool OwnedBySystem(NamedPipeClientStream pipe)
    {
        try
        {
            var owner = pipe.GetAccessControl().GetOwner(typeof(SecurityIdentifier)) as SecurityIdentifier;
            return owner is not null && owner.IsWellKnown(WellKnownSidType.LocalSystemSid);
        }
        catch { return false; }
    }

    /// <summary>The reason picker: a few choices and Send. Null when the person cancels.</summary>
    public static string? PickReason()
    {
        using var form = new Form
        {
            Text = "SAVIO — Ask IT to allow USB writing",
            FormBorderStyle = FormBorderStyle.FixedDialog,
            StartPosition = FormStartPosition.CenterScreen,
            MaximizeBox = false, MinimizeBox = false, ShowInTaskbar = true, TopMost = true,
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(16),
        };
        var layout = new FlowLayoutPanel { FlowDirection = FlowDirection.TopDown, AutoSize = true, WrapContents = false };
        layout.Controls.Add(new Label
        {
            Text = "USB drives are read-only on this PC. IT can allow copying onto them for a while.\nWhy do you need it?",
            AutoSize = true, MaximumSize = new Size(380, 0), Margin = new Padding(0, 0, 0, 8),
        });
        var choices = Reasons.Select((r, i) => new RadioButton { Text = r.Label, Tag = r.Code, AutoSize = true, Checked = i == 0 }).ToList();
        choices.ForEach(c => layout.Controls.Add(c));
        var buttons = new FlowLayoutPanel { FlowDirection = FlowDirection.LeftToRight, AutoSize = true, Margin = new Padding(0, 12, 0, 0) };
        var send = new Button { Text = "Send to IT", DialogResult = DialogResult.OK, AutoSize = true };
        var cancel = new Button { Text = "Cancel", DialogResult = DialogResult.Cancel, AutoSize = true };
        buttons.Controls.Add(send);
        buttons.Controls.Add(cancel);
        layout.Controls.Add(buttons);
        form.Controls.Add(layout);
        form.AcceptButton = send;
        form.CancelButton = cancel;
        return form.ShowDialog() == DialogResult.OK ? choices.First(c => c.Checked).Tag as string : null;
    }
}
