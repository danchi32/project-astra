using AstraAgent.Service.Enrollment;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace AstraAgent.Service.Tests.Enrollment;

/// <summary>Guards how the device names its OS.
///
/// These read the real machine, so they are skipped off Windows (the release workflow builds
/// on ubuntu). That is deliberate: the bug being guarded here — reporting Windows 11 as
/// "Windows 10" — only exists because the old code trusted a value that looks plausible on
/// every platform. A mock would have reproduced the mock, not the mistake.</summary>
public class DeviceIdentityTests
{
    private static WindowsDeviceIdentityProvider Provider() =>
        new(NullLogger<WindowsDeviceIdentityProvider>.Instance);

    [Fact]
    public void OsVersion_NamesTheProductNotTheKernel()
    {
        if (!OperatingSystem.IsWindows()) return;

        var os = Provider().GetOsVersion();

        // "Windows 11 Enterprise 25H2 (build 26200.8893)" — never "Windows 10.0.26200".
        Assert.Contains("Windows", os);
        Assert.Contains("build ", os);
        Assert.DoesNotContain("10.0.", os);

        // The build number the OS actually reports must appear, so the string can be trusted
        // to identify a patch level rather than just read nicely.
        Assert.Contains(Environment.OSVersion.Version.Build.ToString(), os);
    }

    [Fact]
    public void OsVersion_DistinguishesWindows11From10()
    {
        if (!OperatingSystem.IsWindows()) return;
        // Only a client SKU can be 10 or 11. CI runs on a Windows *Server* image, where the
        // correct answer is "Windows Server 20xx" and asserting either would be asserting a fact
        // about the runner rather than about this code. Skip there — OsVersion_NamesTheProduct-
        // NotTheKernel still covers Server, and a developer machine still runs the check below.
        if (!IsClientWindows()) return;

        var os = Provider().GetOsVersion();
        var expected = Environment.OSVersion.Version.Build >= 22000 ? "Windows 11" : "Windows 10";

        // The whole point of the fix: 11 and 10 share kernel version 10.0, and the registry's
        // ProductName still says "Windows 10 Enterprise" on 11. Only the WMI caption (or the
        // build-number fallback) tells them apart.
        Assert.StartsWith(expected, os);
    }

    /// <summary>Client (Windows 10/11) vs Server, straight from the value Windows itself uses to
    /// record which it installed. Reading it through the provider under test would be circular.</summary>
    private static bool IsClientWindows()
    {
        if (!OperatingSystem.IsWindows()) return false;
        try
        {
            using var key = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(
                @"SOFTWARE\Microsoft\Windows NT\CurrentVersion");
            return string.Equals(
                key?.GetValue("InstallationType") as string, "Client", StringComparison.OrdinalIgnoreCase);
        }
        catch
        {
            return false;   // unreadable — treat as "cannot claim client", i.e. skip
        }
    }

    [Fact]
    public void OsVersion_FitsTheColumn()
    {
        if (!OperatingSystem.IsWindows()) return;

        // devices.os_version is varchar(100); an over-long value is rejected by the enrollment
        // schema, which would fail enrollment outright rather than degrade.
        Assert.InRange(Provider().GetOsVersion().Length, 1, 100);
    }
}
