using System;
using System.Windows.Forms;

namespace AstraAgent.Tray;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
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
