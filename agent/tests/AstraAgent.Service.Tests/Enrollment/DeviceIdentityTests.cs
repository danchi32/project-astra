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

        var os = Provider().GetOsVersion();
        var expected = Environment.OSVersion.Version.Build >= 22000 ? "Windows 11" : "Windows 10";

        // The whole point of the fix: 11 and 10 share kernel version 10.0, and the registry's
        // ProductName still says "Windows 10 Enterprise" on 11. Only the WMI caption (or the
        // build-number fallback) tells them apart.
        Assert.StartsWith(expected, os);
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
