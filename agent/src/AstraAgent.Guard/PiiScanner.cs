using System.Text.RegularExpressions;

namespace AstraAgent.Guard;

/// <summary>What a scan can find. The scan reports how many of each, never what they were.</summary>
public enum Finding
{
    Aadhaar,
    Pan,
    Gstin,
    PaymentCard,
    IndianMobile,
    Email,
    BankAccount,   // an IFSC code and an account number on the same line
}

/// <summary>
/// The result of one scan: counts per finding, whether the text looks like a contact list,
/// which admin keywords appeared (by their index in the policy list), and whether the scan was
/// cut short. It holds no text from the input. That is the E4 contract: the scanner may tell
/// the agent *what kind* of thing it saw and how much, never the thing itself.
/// </summary>
public sealed record ScanResult(
    IReadOnlyDictionary<Finding, int> Counts,
    bool ContactList,
    IReadOnlyList<int> KeywordHits,
    bool Truncated,
    bool Incomplete)
{
    public int Total => Counts.Values.Sum();
    public bool Any => Total > 0 || ContactList || KeywordHits.Count > 0;
}

/// <summary>
/// D4 · Detects Indian personal and financial data in text (a paste, a form, a file's text).
///
/// Every detector is a pattern plus a check that the pattern alone can't give:
/// <list type="bullet">
/// <item>Aadhaar: the Verhoeff check digit.</item>
/// <item>GSTIN: its check character.</item>
/// <item>Cards: Luhn.</item>
/// <item>Bank accounts: an IFSC code on the same line.</item>
/// </list>
/// Numbers that are only digits (a 12-digit Aadhaar or a 16-digit card written without
/// spaces) look like order IDs and invoice numbers, and about one in ten passes the checksum
/// by chance. So an unformatted one counts only with a context word nearby ("aadhaar", "card",
/// …). The formatted forms (4-4-4, 4-4-4-4) count on their own.
///
/// Digits are ASCII only (<c>[0-9]</c>, not <c>\d</c>, which in .NET also matches Devanagari and
/// other scripts' digits). Every pattern runs with a timeout. A timed-out scan is reported as
/// <see cref="ScanResult.Incomplete"/>, never as clean.
/// </summary>
public static class PiiScanner
{
    public const int MaxChars = 5_000_000;
    public const int MaxKeywords = 200;
    public const int MaxKeywordLength = 100;
    const int ContextWindow = 40;
    const int ContactListMinLines = 20;
    const double ContactListShare = 0.6;

    static readonly TimeSpan Timeout = TimeSpan.FromMilliseconds(500);
    const RegexOptions Opt = RegexOptions.Compiled | RegexOptions.CultureInvariant;

    static readonly Regex AadhaarRx = new(@"(?<![0-9])(?<n>[2-9][0-9]{3}(?<sep>[ -]?)[0-9]{4}\k<sep>[0-9]{4})(?![0-9])", Opt, Timeout);
    static readonly Regex PanRx = new(@"(?<![A-Za-z0-9])[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z](?![A-Za-z0-9])", Opt, Timeout);
    static readonly Regex GstinRx = new(@"(?<![A-Za-z0-9])[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z](?![A-Za-z0-9])", Opt, Timeout);
    static readonly Regex CardRx = new(@"(?<![0-9])(?:[0-9]{4}([ -])[0-9]{4}\1[0-9]{4}\1[0-9]{1,7}|[0-9]{13,19})(?![0-9])", Opt, Timeout);
    static readonly Regex MobileRx = new(@"(?<![0-9+])(?:\+91[ -]?|0)?[6-9][0-9]{4}[ -]?[0-9]{5}(?![0-9])", Opt, Timeout);
    static readonly Regex EmailRx = new(@"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,24}(?![A-Za-z0-9])", Opt, Timeout);
    static readonly Regex IfscRx = new(@"(?<![A-Za-z0-9])[A-Z]{4}0[A-Z0-9]{6}(?![A-Za-z0-9])", Opt, Timeout);
    static readonly Regex AccountRx = new(@"(?<![0-9])[0-9]{9,18}(?![0-9])", Opt, Timeout);

    static readonly string[] AadhaarWords = { "aadhaar", "aadhar", "adhaar", "uidai", "uid", "आधार" };
    static readonly string[] CardWords = { "card", "visa", "mastercard", "rupay", "amex", "cvv", "expiry", "exp" };

    public static ScanResult Scan(string? text, IReadOnlyList<string>? keywords = null)
    {
        text ??= "";
        bool truncated = text.Length > MaxChars;
        if (truncated) text = text[..MaxChars];

        var counts = Enum.GetValues<Finding>().ToDictionary(f => f, _ => 0);
        bool incomplete = false;
        bool contactList = false;
        var keywordHits = new List<int>();
        try
        {
            counts[Finding.Aadhaar] = AadhaarRx.Matches(text).Count(m => IsAadhaar(m, text));
            counts[Finding.Pan] = PanRx.Matches(text).Count;
            counts[Finding.Gstin] = GstinRx.Matches(text).Count(m => GstinCheck(m.Value));
            counts[Finding.PaymentCard] = CardRx.Matches(text).Count(m => IsCard(m, text));
            counts[Finding.IndianMobile] = MobileRx.Matches(text).Count;
            counts[Finding.Email] = EmailRx.Matches(text).Count;
            counts[Finding.BankAccount] = CountBankAccounts(text);
            contactList = LooksLikeContactList(text);
            keywordHits = MatchKeywords(text, keywords);
        }
        catch (RegexMatchTimeoutException)
        {
            incomplete = true;   // the caller treats this as "could not tell", never as clean
        }
        return new ScanResult(counts, contactList, keywordHits, truncated, incomplete);
    }

    // ── detectors ────────────────────────────────────────────────────────────────────────────

    static bool IsAadhaar(Match m, string text)
    {
        var digits = Digits(m.Groups["n"].Value);
        if (digits.Length != 12 || !Verhoeff(digits)) return false;
        bool formatted = m.Groups["sep"].Value.Length > 0;
        return formatted || NearWord(text, m.Index, m.Length, AadhaarWords);
    }

    static bool IsCard(Match m, string text)
    {
        var digits = Digits(m.Value);
        if (digits.Length is < 13 or > 19 || digits[0] is < '2' or > '6') return false;
        if (digits.All(c => c == digits[0]) || !Luhn(digits)) return false;
        bool formatted = digits.Length != m.Value.Length;
        return formatted || NearWord(text, m.Index, m.Length, CardWords);
    }

    static int CountBankAccounts(string text)
    {
        int n = 0;
        foreach (var line in text.Split('\n'))
        {
            if (line.Length > 2000 || !IfscRx.IsMatch(line)) continue;
            n += AccountRx.Matches(line).Count;
        }
        return n;
    }

    static bool LooksLikeContactList(string text)
    {
        var lines = text.Split('\n').Where(l => l.Trim().Length > 0).ToList();
        if (lines.Count < ContactListMinLines) return false;
        int withContact = lines.Count(l => l.Length < 500 && (MobileRx.IsMatch(l) || EmailRx.IsMatch(l)));
        return withContact >= lines.Count * ContactListShare;
    }

    static List<int> MatchKeywords(string text, IReadOnlyList<string>? keywords)
    {
        var hits = new List<int>();
        if (keywords is null) return hits;
        for (int i = 0; i < Math.Min(keywords.Count, MaxKeywords); i++)
        {
            var k = keywords[i]?.Trim() ?? "";
            if (k.Length is 0 or > MaxKeywordLength) continue;
            // Whole words, any case. The keyword is escaped: an admin's "c++" or "a.b" is literal.
            var rx = new Regex($@"(?<![\p{{L}}\p{{N}}]){Regex.Escape(k)}(?![\p{{L}}\p{{N}}])",
                               RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, Timeout);
            if (rx.IsMatch(text)) hits.Add(i);
        }
        return hits;
    }

    // ── checks ───────────────────────────────────────────────────────────────────────────────

    static string Digits(string s) => new(s.Where(c => c is >= '0' and <= '9').ToArray());

    static bool NearWord(string text, int index, int length, string[] words)
    {
        int start = Math.Max(0, index - ContextWindow);
        int end = Math.Min(text.Length, index + length + ContextWindow);
        var window = text[start..end];
        return words.Any(w => window.Contains(w, StringComparison.OrdinalIgnoreCase));
    }

    static readonly int[,] D =
    {
        {0,1,2,3,4,5,6,7,8,9},{1,2,3,4,0,6,7,8,9,5},{2,3,4,0,1,7,8,9,5,6},{3,4,0,1,2,8,9,5,6,7},
        {4,0,1,2,3,9,5,6,7,8},{5,9,8,7,6,0,4,3,2,1},{6,5,9,8,7,1,0,4,3,2},{7,6,5,9,8,2,1,0,4,3},
        {8,7,6,5,9,3,2,1,0,4},{9,8,7,6,5,4,3,2,1,0},
    };
    static readonly int[,] P =
    {
        {0,1,2,3,4,5,6,7,8,9},{1,5,7,6,2,8,3,0,9,4},{5,8,0,3,7,9,6,1,4,2},{8,9,1,6,0,4,3,5,2,7},
        {9,4,5,3,1,2,6,8,7,0},{4,2,8,6,5,7,3,9,0,1},{2,7,9,3,8,0,6,4,1,5},{7,0,4,6,9,1,3,2,5,8},
    };

    /// <summary>Verhoeff check (Aadhaar's last digit). True when the whole number checks out.</summary>
    public static bool Verhoeff(string digits)
    {
        int c = 0;
        for (int i = 0; i < digits.Length; i++)
            c = D[c, P[i % 8, digits[digits.Length - 1 - i] - '0']];
        return c == 0;
    }

    /// <summary>Luhn check (payment cards).</summary>
    public static bool Luhn(string digits)
    {
        int sum = 0;
        bool dbl = false;
        for (int i = digits.Length - 1; i >= 0; i--)
        {
            int d = digits[i] - '0';
            if (dbl) { d *= 2; if (d > 9) d -= 9; }
            sum += d;
            dbl = !dbl;
        }
        return sum % 10 == 0;
    }

    const string Base36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

    /// <summary>GSTIN check character (the 15th), computed from the first 14.</summary>
    public static bool GstinCheck(string gstin)
    {
        if (gstin.Length != 15) return false;
        int sum = 0;
        for (int i = 0; i < 14; i++)
        {
            int v = Base36.IndexOf(gstin[i]);
            if (v < 0) return false;
            int p = v * (i % 2 == 0 ? 1 : 2);
            sum += p / 36 + p % 36;
        }
        return Base36[(36 - sum % 36) % 36] == gstin[14];
    }
}
