using System.Diagnostics;
using AstraAgent.Service.Net;
using AstraAgent.Service.Remediation;
using AstraAgent.Service.Security;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>Phase 1 security review (1f) — agent-side fixes.</summary>
public class SecurityReviewFixTests
{
    [Fact]
    public void Install_RefusesAWellFormedIdThatIsNotInTheAgentsOwnCatalog()
    {
        // Shaped like a winget id, so it passes the old check — the agent must still refuse it.
        var (ok, msg) = PackageInstaller.Install("AnyDesk.AnyDesk");
        Assert.False(ok);
        Assert.Contains("not in this agent's software catalog", msg);
    }

    [Fact]
    public void FindWinget_ComparesVersionsAsVersions()
    {
        Assert.True(PackageInstaller.VersionOf(@"C:\x\Microsoft.DesktopAppInstaller_1.10.3.0_x64__8wekyb3d8bbwe")
                    > PackageInstaller.VersionOf(@"C:\x\Microsoft.DesktopAppInstaller_1.9.25.0_x64__8wekyb3d8bbwe"));
    }

    [Fact]
    public void Limiter_CapsManualRunsPerHour()
    {
        var t = DateTimeOffset.Parse("2026-11-11T10:00:00Z");
        var lim = new FixLimiter(() => t);
        for (var i = 0; i < FixLimiter.MaxManualPerHour; i++)
        {
            Assert.Null(lim.RefuseLadder(true));
            t = t.AddMinutes(3);
        }
        Assert.NotNull(lim.RefuseLadder(true));                 // the 7th click in an hour
        t = t.AddMinutes(61);
        Assert.Null(lim.RefuseLadder(true));
    }

    [Fact]
    public void Journal_SkipsABadLine_KeepsTheRest_AndIsCapped()
    {
        var path = Path.Combine(Path.GetTempPath(), $"savio-journal-{Guid.NewGuid():N}.jsonl");
        var doctor = new NetworkDoctor(NullLogger<NetworkDoctor>.Instance, _ => Task.FromResult(true),
            path, new FixLimiter(() => DateTimeOffset.UtcNow));
        try
        {
            doctor.Journal(new JournalEntry(DateTimeOffset.UtcNow, "test", "DnsFailing", "FlushDns", true, null, false));
            File.AppendAllText(path, "{ not json\n");
            doctor.Journal(new JournalEntry(DateTimeOffset.UtcNow, "test", "DnsFailing", "RenewIp", true, null, true));
            Assert.Equal(2, doctor.ReadJournal().Count);         // one bad line no longer hides both

            for (var i = 0; i < NetworkDoctor.MaxJournalEntries + 50; i++)
                doctor.Journal(new JournalEntry(DateTimeOffset.UtcNow, "test", "NoAddress", null, null, null, false));
            Assert.Equal(NetworkDoctor.MaxJournalEntries, File.ReadAllLines(path).Length);

            doctor.KeepJournal(doctor.ReadJournal().Take(3));
            Assert.Equal(3, doctor.ReadJournal().Count);
        }
        finally { File.Delete(path); }
    }

    [Fact]
    public void SecureDirectory_RefusesAJunction()
    {
        var target = Directory.CreateTempSubdirectory("savio-target-").FullName;
        var link = Path.Combine(Path.GetTempPath(), $"savio-junction-{Guid.NewGuid():N}");
        try
        {
            using (var p = Process.Start(new ProcessStartInfo("cmd.exe", $"/c mklink /J \"{link}\" \"{target}\"")
                   { CreateNoWindow = true, UseShellExecute = false })!) p.WaitForExit();
            Assert.True(Directory.Exists(link));
            Assert.Throws<IOException>(() => SecureDirectory.Ensure(link));
        }
        finally
        {
            if (Directory.Exists(link)) Directory.Delete(link);
            Directory.Delete(target, true);
        }
    }

    [Fact]
    public void Journal_And_WingetTemp_LiveUnderTheInstallRoot_NotProgramData()
    {
        var programData = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
        Assert.False(SecureDirectory.StateRoot.StartsWith(programData, StringComparison.OrdinalIgnoreCase));
    }
}
