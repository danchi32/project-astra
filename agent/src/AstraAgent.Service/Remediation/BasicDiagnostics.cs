using System;
using System.Diagnostics;
using System.Linq;

namespace AstraAgent.Service.Remediation;

/// <summary>The first-line repairs a technician runs before anything else: sound, DHCP,
/// a hardware rescan, and a system file check.
///
/// All four need elevation, so they live in the service rather than the Tray. None of them
/// takes a parameter — the target is fixed by the action id, which is what keeps them safe
/// without an allowlist of their own: there is no name for a caller to influence.</summary>
public static class BasicDiagnostics
{
    /// <summary>Brings the audio stack back.
    ///
    /// Two services, in this order and not the other one. Windows Audio (Audiosrv) DEPENDS on
    /// the Audio Endpoint Builder, which is the one that enumerates playback and recording
    /// devices — so when sound is gone because Windows lost track of the speakers, restarting
    /// Audiosrv alone fixes nothing. Restarting the endpoint builder rebuilds the device list
    /// and, via ServiceRestarter's dependent handling, carries Audiosrv down and back up with
    /// it.
    ///
    /// Audiosrv is then restarted explicitly rather than relying on that. If it was already
    /// stopped before we started — which is itself a common cause of silence — it was never a
    /// running dependent, so nothing would have brought it back.</summary>
    public static (bool Success, string Output) RestartAudio()
    {
        var (builderOk, builderMsg) = ServiceRestarter.Restart("AudioEndpointBuilder");
        if (!builderOk)
            return (false, $"Could not restart the audio endpoint service: {builderMsg}");

        var (audioOk, audioMsg) = ServiceRestarter.Restart("Audiosrv");
        if (!audioOk)
            // The endpoint builder is running and the device list is rebuilt, but without
            // Audiosrv there is still no sound. That is a failure, not a partial win.
            return (false,
                "Rebuilt the audio device list, but Windows Audio did not come back: "
                + audioMsg);

        return (true,
            "Audio endpoint builder and Windows Audio are both running; the playback and "
            + "recording device list has been rebuilt.");
    }

    /// <summary>Drops the current DHCP lease and asks for a new one.
    ///
    /// The middle rung between flushing DNS (which touches nothing but the resolver cache)
    /// and bouncing the adapter (which takes the link down). It fixes the common case where
    /// the machine is holding an address from a network it is no longer on — a stale lease
    /// after a VPN, a docking station, or a move between offices.
    ///
    /// The release cuts the connection for a moment, including this agent's own. That is
    /// expected: the result is reported once the link returns.</summary>
    public static (bool Success, string Output) RenewIpAddress()
    {
        // /renew ALONE first, and usually only this.
        //
        // `ipconfig /release` takes no adapter here, so it drops the lease on every
        // DHCP-enabled interface at once — the VPN tunnel, the Hyper-V and WSL switches, the
        // dock. The action exists partly for "the address is stale after a VPN", which is
        // exactly the case where releasing everything cuts the tunnel it was meant to
        // recover from. /renew re-requests the lease without ever leaving the machine
        // without an address, so there is no window in which the PC is offline.
        var (renewOk, renewOut) = Run("ipconfig.exe", "/renew");
        if (renewOk)
        {
            var got = FirstIPv4(renewOut);
            return (true, got is null
                ? "Renewed the DHCP lease with the network."
                : $"Renewed the DHCP lease with the network: {got}.");
        }

        // Only now the destructive path: a renew that fails usually means the server will
        // not extend THIS lease, and releasing it first is what makes the next request a new
        // one rather than a repeat.
        var (releaseOk, releaseOut) = Run("ipconfig.exe", "/release");
        if (!releaseOk)
            return (false,
                $"The DHCP lease could not be renewed ({renewOut.Trim()}) and the old address "
                + $"could not be released either: {releaseOut}");

        var (retryOk, retryOut) = Run("ipconfig.exe", "/renew");
        if (!retryOk)
            // Released but not renewed leaves the machine with no address at all, which is
            // worse than where it started. Say so plainly and name the way out.
            return (false,
                $"The old IP address was released but a new one could not be obtained: {retryOut} "
                + "The PC may now be offline — check that the network cable or Wi-Fi is "
                + "connected, then restart the PC.");

        var address = FirstIPv4(retryOut);
        return (true, address is null
            ? "Released the stale DHCP lease and obtained a new one from the network."
            : $"Released the stale DHCP lease and obtained a new one: {address}.");
    }

    /// <summary>Triggers the same hardware rescan as Device Manager's "Scan for hardware
    /// changes".
    ///
    /// This is the fix for a device that is physically attached and simply not being seen —
    /// a headset, a monitor, a USB dock. It only asks Windows to re-enumerate what is
    /// present; it installs nothing and changes no driver, which is why it is safe to run
    /// without approval. Fixing a device that is present but FAILED is a different job and
    /// needs the device's instance id, which the agent does not collect.</summary>
    public static (bool Success, string Output) RescanDevices()
    {
        var (ok, output) = Run("pnputil.exe", "/scan-devices");
        if (!ok)
            return (false,
                $"The hardware rescan could not be started: {output} "
                + "On older Windows builds pnputil may not support /scan-devices.");

        return (true,
            "Asked Windows to re-enumerate connected hardware, the same scan Device Manager "
            + "runs. Anything attached but not previously detected is picked up now.");
    }

    /// <summary>Runs System File Checker over the protected Windows files.
    ///
    /// Long — typically ten to thirty minutes — but it is the check that answers "is Windows
    /// itself damaged" and it repairs what it finds from the local component store. Gated
    /// behind approval because of the runtime and the disk load, not because it is risky:
    /// SFC only ever replaces a protected file with the known-good copy.
    ///
    /// ponytail: SFC only. When it reports damage it cannot repair, the component store it
    /// repairs FROM is itself broken and the next step is
    /// `DISM /Online /Cleanup-Image /RestoreHealth` before re-running SFC. That is a second
    /// long-running command inside the same 60-minute task ceiling, so it is left to a
    /// technician for now; make it its own action if the "could not fix" branch turns out to
    /// be common in practice.</summary>
    public static (bool Success, string Output) RepairSystemFiles()
    {
        var (ok, output) = Run("sfc.exe", "/scannow", timeoutMs: 45 * 60 * 1000);
        if (!ok)
            return (false, $"The system file check could not be completed: {output}");
        return InterpretSfc(output);
    }

    /// <summary>Turns SFC's report into an outcome.
    ///
    /// Pure, so the three endings can be tested without a broken Windows install to produce
    /// them. The exit code is not the signal — SFC exits 0 whether it found nothing, repaired
    /// everything, or gave up on a file — so the wording is all there is to go on, and the
    /// "could not fix" ending must never be reported as a success: that is precisely the case
    /// where somebody has to look at the machine.</summary>
    internal static (bool Success, string Output) InterpretSfc(string output)
    {
        // sfc.exe writes UTF-16, which arrives interleaved with NUL bytes when the console
        // redirects it. Run() already strips them; doing it again here is what keeps every
        // branch below reachable if this is ever called from somewhere that does not, since
        // the failure mode is silent — every real machine falls through to "unrecognised".
        var text = (output ?? string.Empty).Replace("\0", string.Empty).ToLowerInvariant();

        if (text.Contains("unable to fix") || text.Contains("were not able to be fixed"))
            return (false,
                "Windows found damaged system files and could not repair all of them. The "
                + "component store they are restored from is likely damaged too — this needs "
                + "a technician to run a component store repair (DISM) and check CBS.log.");

        if (text.Contains("successfully repaired"))
            return (true,
                "Windows found damaged system files and repaired them from the local component "
                + "store. A restart is needed for the replaced files to be in use.");

        if (text.Contains("did not find any integrity violations"))
            return (true,
                "Windows verified every protected system file and found no damage, so the "
                + "problem lies above the operating system rather than in it.");

        if (text.Contains("could not perform") || text.Contains("another servicing"))
            return (false,
                "Windows could not run the check because another servicing operation is in "
                + "progress. Let Windows Update finish, then try again.");

        // An ending nobody has seen yet. Reporting it as a success would claim a verification
        // that did not happen, so hand the raw text on instead of guessing at it.
        var snippet = (output ?? string.Empty).Trim();
        return (false,
            "The system file check finished with a result this agent does not recognise: "
            + (snippet.Length > 300 ? snippet[..300] : snippet));
    }

    /// <summary>The first IPv4 address in ipconfig's output, or null. Best-effort: it only
    /// enriches the success message, so a parse that finds nothing costs nothing.</summary>
    internal static string? FirstIPv4(string? output)
        => (output ?? string.Empty)
            .Split('\n')
            .Select(line => line.Trim())
            .Where(line => line.Contains("IPv4", StringComparison.OrdinalIgnoreCase)
                        && line.Contains(':'))
            .Select(line => line[(line.IndexOf(':') + 1)..].Trim().TrimEnd('.'))
            .FirstOrDefault(v => v.Length > 0 && v.Count(c => c == '.') == 3 && !v.StartsWith("0."));

    /// <summary>Runs one of the fixed executables above and returns its combined output.
    ///
    /// Arguments go in as separate argv elements, never a command string — none of the
    /// callers here take user input, and keeping the habit is what stops the next one that
    /// does from being the exception.</summary>
    private static (bool Ok, string Output) Run(string exe, string arg, int timeoutMs = 120000)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = exe,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };
            psi.ArgumentList.Add(arg);

            using var process = Process.Start(psi);
            if (process is null) return (false, $"could not start {exe}");

            // Both pipes drained CONCURRENTLY. Reading stdout to EOF first blocks until the
            // child exits, and a child that fills the stderr pipe buffer meanwhile blocks
            // writing and never exits — so the two wait on each other forever and the
            // timeout below, which is the only thing that kills a wedged sfc, is never
            // reached.
            var stdoutTask = process.StandardOutput.ReadToEndAsync();
            var stderrTask = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(timeoutMs))
            {
                try { process.Kill(entireProcessTree: true); } catch { /* already gone */ }
                return (false, $"{exe} did not finish within {timeoutMs / 60000} minutes.");
            }

            // sfc.exe writes UTF-16, which arrives here interleaved with NUL bytes when the
            // console redirects it. Stripping them is what makes the text matchable at all.
            var combined =
                (stdoutTask.GetAwaiter().GetResult() + "\n" + stderrTask.GetAwaiter().GetResult())
                    .Replace("\0", string.Empty);

            if (process.ExitCode != 0)
                return (false, $"{exe} exited with {process.ExitCode}. {combined.Trim()}");

            return (true, combined);
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
    }
}
