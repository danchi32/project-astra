// Phase 3 · Spike 3: how fast are the D4 detectors, and how much memory do they need?
//
// The detectors: Aadhaar (12 digits + Verhoeff), PAN, GSTIN (+ check character), card (Luhn),
// +91 mobile, email, IFSC, plus a "contact list" heuristic (many lines each holding a name
// and a phone/email). They are regular expressions plus checksums: no ML model. This
// measures them on synthetic text of paste and file sizes, on one core at below-normal
// priority, to approximate a low-end PC.
//
// Run:  dotnet run -c Release -- [--one-core]
using System.Diagnostics;
using System.IO.Compression;
using System.Text;
using System.Text.RegularExpressions;

static class Detectors
{
    const RegexOptions O = RegexOptions.Compiled | RegexOptions.CultureInvariant;
    static readonly Regex Aadhaar = new(@"(?<!\d)[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?!\d)", O);
    static readonly Regex Pan = new(@"(?<![A-Z0-9])[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z](?![A-Z0-9])", O);
    static readonly Regex Gstin = new(@"(?<![A-Z0-9])\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z](?![A-Z0-9])", O);
    static readonly Regex Card = new(@"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)", O);
    static readonly Regex Mobile = new(@"(?<!\d)(?:\+91[ -]?|0)?[6-9]\d{9}(?!\d)", O);
    static readonly Regex Email = new(@"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24}", O);
    static readonly Regex Ifsc = new(@"(?<![A-Z0-9])[A-Z]{4}0[A-Z0-9]{6}(?![A-Z0-9])", O);

    static readonly int[,] D = {
        {0,1,2,3,4,5,6,7,8,9},{1,2,3,4,0,6,7,8,9,5},{2,3,4,0,1,7,8,9,5,6},{3,4,0,1,2,8,9,5,6,7},
        {4,0,1,2,3,9,5,6,7,8},{5,9,8,7,6,0,4,3,2,1},{6,5,9,8,7,1,0,4,3,2},{7,6,5,9,8,2,1,0,4,3},
        {8,7,6,5,9,3,2,1,0,4},{9,8,7,6,5,4,3,2,1,0}};
    static readonly int[,] P = {
        {0,1,2,3,4,5,6,7,8,9},{1,5,7,6,2,8,3,0,9,4},{5,8,0,3,7,9,6,1,4,2},{8,9,1,6,0,4,3,5,2,7},
        {9,4,5,3,1,2,6,8,7,0},{4,2,8,6,5,7,3,9,0,1},{2,7,9,3,8,0,6,4,1,5},{7,0,4,6,9,1,3,2,5,8}};

    static string Digits(string s) => new(s.Where(char.IsAsciiDigit).ToArray());

    public static bool Verhoeff(string num)
    {
        int c = 0;
        for (int i = 0; i < num.Length; i++)
            c = D[c, P[i % 8, num[num.Length - 1 - i] - '0']];
        return c == 0;
    }

    public static bool Luhn(string num)
    {
        int sum = 0; bool alt = false;
        for (int i = num.Length - 1; i >= 0; i--)
        {
            int d = num[i] - '0';
            if (alt) { d *= 2; if (d > 9) d -= 9; }
            sum += d; alt = !alt;
        }
        return sum % 10 == 0;
    }

    const string Gst36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    public static bool GstinCheck(string g)
    {
        int sum = 0;
        for (int i = 0; i < 14; i++)
        {
            int v = Gst36.IndexOf(g[i]) * (i % 2 == 0 ? 1 : 2);
            sum += v / 36 + v % 36;
        }
        return Gst36[(36 - sum % 36) % 36] == g[14];
    }

    public record Counts(int Aadhaar, int Pan, int Gstin, int Card, int Mobile, int Email, int Ifsc, bool ContactList);

    public static Counts Scan(string text)
    {
        int aad = Aadhaar.Matches(text).Count(m => Verhoeff(Digits(m.Value)));
        int pan = Pan.Matches(text).Count;
        int gst = Gstin.Matches(text).Count(m => GstinCheck(m.Value));
        int card = Card.Matches(text).Count(m => { var d = Digits(m.Value); return d.Length is >= 13 and <= 19 && Luhn(d); });
        int mob = Mobile.Matches(text).Count;
        int mail = Email.Matches(text).Count;
        int ifsc = Ifsc.Matches(text).Count;
        // Contact list: at least 20 lines, and at least 60% of them carry a phone or e-mail.
        var lines = text.Split('\n');
        int withContact = lines.Count(l => l.Length < 400 && (Mobile.IsMatch(l) || Email.IsMatch(l)));
        bool list = lines.Length >= 20 && withContact >= lines.Length * 0.6;
        return new(aad, pan, gst, card, mob, mail, ifsc, list);
    }
}

static class Synth
{
    static readonly Random R = new(42);
    static readonly string[] Words = "the invoice for march payment due please find attached report meeting client account balance transfer approved pending review office team update".Split(' ');

    static string Aadhaar()
    {
        // 11 random digits + the Verhoeff check digit that makes it valid.
        var b = R.Next(2, 10) + string.Concat(Enumerable.Range(0, 10).Select(_ => R.Next(10)));
        for (int c = 0; c < 10; c++) if (Detectors.Verhoeff(b + c)) return $"{b[..4]} {b[4..8]} {b[8..]}{c}";
        return b + "0";
    }

    public static string Prose(int bytes, double piiRate)
    {
        var sb = new StringBuilder(bytes + 256);
        while (sb.Length < bytes)
        {
            for (int i = 0; i < 12; i++) sb.Append(Words[R.Next(Words.Length)]).Append(' ');
            if (R.NextDouble() < piiRate)
            {
                switch (R.Next(5))
                {
                    case 0: sb.Append(Aadhaar()); break;
                    case 1: sb.Append("ABCPE").Append(R.Next(1000, 9999)).Append('F'); break;
                    case 2: sb.Append("4111 1111 1111 1111"); break;
                    case 3: sb.Append("+91 9").Append(R.Next(100000000, 999999999)); break;
                    case 4: sb.Append("person").Append(R.Next(9999)).Append("@example.com"); break;
                }
            }
            sb.Append(".\n");
        }
        return sb.ToString(0, bytes);
    }

    public static string ContactList(int rows) =>
        string.Join('\n', Enumerable.Range(0, rows).Select(i => $"Customer {i},+91 9{R.Next(100000000, 999999999)},c{i}@example.com,Pune"));

    public static byte[] Docx(string text)
    {
        using var ms = new MemoryStream();
        using (var zip = new ZipArchive(ms, ZipArchiveMode.Create, true))
        {
            var e = zip.CreateEntry("word/document.xml");
            using var w = new StreamWriter(e.Open());
            w.Write("<w:document xmlns:w=\"x\"><w:body>");
            foreach (var para in text.Split('\n')) w.Write($"<w:p><w:r><w:t>{System.Security.SecurityElement.Escape(para)}</w:t></w:r></w:p>");
            w.Write("</w:body></w:document>");
        }
        return ms.ToArray();
    }

    // What the file scanner would do for a .docx: unzip, strip tags, scan.
    public static string DocxText(byte[] docx)
    {
        using var zip = new ZipArchive(new MemoryStream(docx));
        using var r = new StreamReader(zip.GetEntry("word/document.xml")!.Open());
        return Regex.Replace(r.ReadToEnd(), "<[^>]+>", " ");
    }
}

static class Program
{
    static double Ms(Action a, int reps)
    {
        a();                                              // warm-up (JIT, regex compilation)
        var sw = Stopwatch.StartNew();
        for (int i = 0; i < reps; i++) a();
        return sw.Elapsed.TotalMilliseconds / reps;
    }

    static void Main(string[] args)
    {
        var proc = Process.GetCurrentProcess();
        if (args.Contains("--one-core"))
        {
            proc.ProcessorAffinity = (IntPtr)1;
            proc.PriorityClass = ProcessPriorityClass.BelowNormal;
        }
        Console.WriteLine($"cores used: {(args.Contains("--one-core") ? "1 (BelowNormal)" : Environment.ProcessorCount.ToString())}");
        var startup = Stopwatch.StartNew();
        Detectors.Scan("warm");                           // first-use cost: static regex construction
        Console.WriteLine($"first scan (regex build + JIT): {startup.Elapsed.TotalMilliseconds:F0} ms");

        Console.WriteLine("\npaste-sized text (1 PII item per ~10 lines):");
        foreach (var size in new[] { 1_000, 10_000, 100_000, 1_000_000 })
        {
            var text = Synth.Prose(size, 0.1);
            var ms = Ms(() => Detectors.Scan(text), size >= 1_000_000 ? 5 : 50);
            Console.WriteLine($"  {size,9:N0} chars: {ms,8:F2} ms  ({size / 1e6 / (ms / 1000):F1} MB/s)");
        }

        var c = Detectors.Scan(Synth.Prose(100_000, 0.1));
        Console.WriteLine($"\nfound in 100k chars: aadhaar={c.Aadhaar} pan={c.Pan} card={c.Card} mobile={c.Mobile} email={c.Email}");
        var list = Synth.ContactList(500);
        Console.WriteLine($"contact list of 500 rows detected: {Detectors.Scan(list).ContactList}; " +
                          $"prose detected as list: {Detectors.Scan(Synth.Prose(50_000, 0.1)).ContactList}");

        Console.WriteLine("\nfile scan (.docx of ~200 KB text: unzip + strip tags + scan):");
        var docx = Synth.Docx(Synth.Prose(200_000, 0.05));
        var perFile = Ms(() => Detectors.Scan(Synth.DocxText(docx)), 20);
        Console.WriteLine($"  {perFile:F1} ms per file -> {1000 / perFile:F0} files/s, ~{3600 * 1000 / perFile:N0} files/hour on this setting");

        GC.Collect();
        proc.Refresh();
        Console.WriteLine($"\nmemory: working set {proc.WorkingSet64 / 1048576.0:F0} MB, managed heap {GC.GetTotalMemory(true) / 1048576.0:F1} MB, peak working set {proc.PeakWorkingSet64 / 1048576.0:F0} MB");
    }
}
