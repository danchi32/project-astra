using System;
using System.Windows.Forms;
using AstraAgent.Tray.Update;

namespace AstraAgent.Tray;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        // Hand off to the user-writable live copy so the tray can self-update. If this returns
        // true it already launched that copy — this seed instance should just exit.
        if (TrayBootstrap.HandoffIfNeeded())
            return;

        ApplicationConfiguration.Initialize();
        try
        {
            Application.Run(new TrayApplicationContext());
        }
        catch (Exception ex)
        {
            // Surface startup failures instead of exiting silently with no icon.
            MessageBox.Show(
                "ASTRA Assistant failed to start:\n\n" + ex.Message,
                "ASTRA Assistant", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
