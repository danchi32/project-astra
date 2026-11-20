namespace AstraAgent.Guard;

/// <summary>
/// Phase 3 · D7: the approvals in force for one Windows account, as the service stores them
/// and the native host reads them. One entry per approval: <c>site|channel|unix-seconds-until</c>.
///
/// Where they live (both sides agree on it here): <c>HKLM\SOFTWARE\SAVIO\GuardApprovals\&lt;SID&gt;</c>,
/// REG_MULTI_SZ <c>Approvals</c>. The service writes the key and lets only that account (plus
/// SYSTEM and Administrators) read it, so one person's approvals are not another's to see.
/// </summary>
public static class GuardApprovals
{
    public const string KeyPath = @"SOFTWARE\SAVIO\GuardApprovals";
    public const string ValueName = "Approvals";

    public static string Format(string site, string channel, DateTimeOffset until) =>
        $"{site}|{channel}|{until.ToUnixTimeSeconds()}";

    /// <summary>True when an entry for exactly this site and channel is still in force.</summary>
    public static bool Allows(IEnumerable<string>? entries, string site, string channel, DateTimeOffset now)
    {
        foreach (var entry in entries ?? [])
        {
            var parts = entry.Split('|');
            if (parts.Length == 3 && parts[0] == site && parts[1] == channel &&
                long.TryParse(parts[2], out var until) && now.ToUnixTimeSeconds() < until)
                return true;
        }
        return false;
    }
}
