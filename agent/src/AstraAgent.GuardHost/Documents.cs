using System.IO.Compression;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using AstraAgent.Guard;
using UglyToad.PdfPig;
using UglyToad.PdfPig.DocumentLayoutAnalysis.TextExtractor;

namespace AstraAgent.GuardHost;

/// <summary>
/// Phase 3 · D3 / D5: the text inside a document, for the scanner. Word and Excel (.docx /
/// .xlsx) always; PDF only where the org turned it on. Read in memory; nothing is written.
///
/// These are files from anywhere, so a document that is too big, is not what its name says,
/// is encrypted, or takes too long is null: "could not check", never "clean".
/// </summary>
public static class Documents
{
    public const long MaxBytes = 20 * 1024 * 1024;
    public const int MaxPdfPages = 500;
    public static readonly TimeSpan PdfTimeout = TimeSpan.FromSeconds(10);

    public static bool Readable(string ext, bool pdf) =>
        ext.Equals(".docx", StringComparison.OrdinalIgnoreCase) || ext.Equals(".xlsx", StringComparison.OrdinalIgnoreCase) ||
        (pdf && ext.Equals(".pdf", StringComparison.OrdinalIgnoreCase));

    /// <summary>The document's text, or null, also when it is longer than the scanner reads.</summary>
    public static string? Text(byte[] bytes, string ext, bool pdf)
    {
        if (bytes.Length > MaxBytes || !Readable(ext, pdf)) return null;
        try
        {
            return ext.Equals(".pdf", StringComparison.OrdinalIgnoreCase) ? PdfText(bytes) : OfficeText(bytes, ext);
        }
        catch (Exception ex) when (ex is InvalidDataException or IOException or ArgumentException) { return null; }
    }

    static string? OfficeText(byte[] bytes, string ext)
    {
        using var zip = new ZipArchive(new MemoryStream(bytes), ZipArchiveMode.Read);
        var parts = ext.Equals(".docx", StringComparison.OrdinalIgnoreCase)
            ? zip.Entries.Where(e => e.FullName == "word/document.xml")
            : zip.Entries.Where(e => e.FullName == "xl/sharedStrings.xml" ||
                                     (e.FullName.StartsWith("xl/worksheets/sheet") && e.FullName.EndsWith(".xml")));
        var sb = new StringBuilder();
        foreach (var entry in parts)
        {
            // A zip bomb is refused by its declared size before anything is inflated, and the
            // read itself stops at the cap whatever the entry claims (security review L1).
            if (entry.Length > MaxBytes || sb.Length > PiiScanner.MaxChars) return null;
            using var reader = new StreamReader(entry.Open());
            var buffer = new char[(int)Math.Min(MaxBytes, PiiScanner.MaxChars) + 1];
            int read = 0, n;
            while (read < buffer.Length && (n = reader.Read(buffer, read, buffer.Length - read)) > 0) read += n;
            // More than the scanner reads: "could not check", never the start standing in for the
            // whole (review H3).
            if (read == buffer.Length) return null;
            sb.Append(XmlText(new string(buffer, 0, read))).Append('\n');
        }
        return Fits(sb.ToString());
    }

    /// <summary>
    /// A PDF parser reading someone else's file: on its own thread, with a time limit and a page
    /// limit, and any failure is "could not check". The browser starts a fresh host per check, so
    /// a parse that overruns ends with that process.
    /// ponytail: the overrunning thread is abandoned, not stopped (PdfPig has no cancellation). In
    /// the weekly map it can keep a core busy until the run ends; upgrade path is parsing each PDF
    /// in a child process that is killed at the limit.
    /// </summary>
    static string? PdfText(byte[] bytes)
    {
        var work = Task.Run(() =>
        {
            try
            {
                using var doc = PdfDocument.Open(bytes);
                if (doc.NumberOfPages > MaxPdfPages) return null;
                var sb = new StringBuilder();
                foreach (var page in doc.GetPages())
                {
                    sb.Append(ContentOrderTextExtractor.GetText(page)).Append('\n');
                    if (sb.Length > PiiScanner.MaxChars) return null;   // longer than the scanner reads (H3)
                }
                return sb.ToString();
            }
#pragma warning disable CA1031 // a parser of untrusted input: whatever it throws means "could not check"
            catch (Exception) { return null; }
#pragma warning restore CA1031
        });
        return work.Wait(PdfTimeout) ? work.Result : null;
    }

    static readonly Regex LineEnd = new(@"</(w:p|row|si)>", RegexOptions.Compiled);
    static readonly Regex CellEnd = new(@"</c>", RegexOptions.Compiled);
    static readonly Regex Tag = new(@"<[^>]{0,2000}>", RegexOptions.Compiled);

    /// <summary>Word paragraphs and Excel rows become lines, cells become tabs, tags go.</summary>
    static string XmlText(string xml) =>
        WebUtility.HtmlDecode(Tag.Replace(CellEnd.Replace(LineEnd.Replace(xml, "\n"), "\t"), ""));

    /// <summary>The text if the scanner reads all of it, else null: "could not check" (review H3).</summary>
    internal static string? Fits(string s) => s.Length > PiiScanner.MaxChars ? null : s;
}
