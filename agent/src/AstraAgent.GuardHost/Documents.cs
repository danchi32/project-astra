using System.IO.Compression;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using System.Xml;
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
        catch (Exception ex) when (ex is InvalidDataException or IOException or ArgumentException or XmlException) { return null; }
    }

    static string? OfficeText(byte[] bytes, string ext)
    {
        using var zip = new ZipArchive(new MemoryStream(bytes), ZipArchiveMode.Read);
        if (!ext.Equals(".docx", StringComparison.OrdinalIgnoreCase)) return XlsxText(zip);
        var sb = new StringBuilder();
        foreach (var entry in zip.Entries.Where(e => e.FullName == "word/document.xml"))
        {
            if (Entry(entry) is not { } xml) return null;
            sb.Append(XmlText(xml)).Append('\n');
        }
        return Fits(sb.ToString());
    }

    /// <summary>One part of the zip as text, or null when it is bigger than the scanner reads. A
    /// zip bomb is refused by its declared size before anything is inflated, and the read itself
    /// stops at the cap whatever the entry claims (security review L1, review 3b H3).</summary>
    static string? Entry(ZipArchiveEntry entry)
    {
        if (entry.Length > MaxBytes) return null;
        using var reader = new StreamReader(entry.Open());
        var buffer = new char[(int)Math.Min(MaxBytes, PiiScanner.MaxChars) + 1];
        int read = 0, n;
        while (read < buffer.Length && (n = reader.Read(buffer, read, buffer.Length - read)) > 0) read += n;
        return read == buffer.Length ? null : new string(buffer, 0, read);
    }

    const int MaxColumns = 1000;

    /// <summary>
    /// Security review (3b) H4: a sheet as the person sees it. Each row is one line, its cells
    /// split by tabs in their columns, with shared strings put back in their cells; sheets are
    /// split by a form feed. So an IFSC code and an account number are on one line, and a
    /// column's heading is the first line of its sheet, which is what the scanner reads a
    /// number's meaning from (<c>PiiScanner.InColumn</c>). Numbers alone, away from "Aadhaar"
    /// or "IFSC", were never counted. The XML is read with DTDs prohibited.
    /// </summary>
    static string? XlsxText(ZipArchive zip)
    {
        var settings = new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null };
        var shared = new List<string>();
        if (zip.GetEntry("xl/sharedStrings.xml") is { } sst)
        {
            if (Entry(sst) is not { } xml) return null;
            using var r = XmlReader.Create(new StringReader(xml), settings);
            StringBuilder? si = null;
            // ReadElementContentAsString leaves the reader on the next node already, so the loop
            // reads only when nothing was consumed.
            r.Read();
            while (!r.EOF)
            {
                if (r.NodeType == XmlNodeType.Element && r.LocalName == "t" && si is not null) { si.Append(r.ReadElementContentAsString()); continue; }
                if (r.NodeType == XmlNodeType.Element && r.LocalName == "si") si = new StringBuilder();
                else if (r.NodeType == XmlNodeType.EndElement && r.LocalName == "si" && si is not null) { shared.Add(si.ToString()); si = null; }
                r.Read();
            }
        }
        var used = new bool[shared.Count];
        var sb = new StringBuilder();
        foreach (var entry in zip.Entries.Where(e => e.FullName.StartsWith("xl/worksheets/sheet") && e.FullName.EndsWith(".xml")))
        {
            if (Entry(entry) is not { } xml) return null;
            using var r = XmlReader.Create(new StringReader(xml), settings);
            int col = 0, at = 0;
            string? type = null;
            r.Read();
            while (!r.EOF)
            {
                if (r.NodeType == XmlNodeType.Element && r.LocalName is "v" or "t")
                {
                    var value = r.ReadElementContentAsString();
                    if (type == "s" && int.TryParse(value, out var i) && i >= 0 && i < shared.Count) { value = shared[i]; used[i] = true; }
                    for (; at < Math.Min(col, MaxColumns); at++) sb.Append('\t');
                    sb.Append(value.Replace('\t', ' ').Replace('\n', ' ').Replace('\f', ' '));
                    if (sb.Length > PiiScanner.MaxChars) return null;
                    continue;
                }
                if (r.NodeType == XmlNodeType.Element && r.LocalName == "row") { if (sb.Length > 0 && sb[^1] != '\f') sb.Append('\n'); at = 0; }
                else if (r.NodeType == XmlNodeType.Element && r.LocalName == "c")
                {
                    type = r.GetAttribute("t");
                    col = Column(r.GetAttribute("r")) ?? at;
                }
                r.Read();
            }
            sb.Append('\f');
        }
        // Text no cell shows (a deleted cell's string, a sheet that was not read) is scanned too,
        // one string a line: hidden is not the same as gone.
        for (int i = 0; i < shared.Count; i++)
            if (!used[i]) sb.Append(shared[i].Replace('\f', ' ')).Append('\n');
        return Fits(sb.ToString());
    }

    /// <summary>"C7" → 2; null for anything that is not a cell reference.</summary>
    static int? Column(string? reference)
    {
        if (string.IsNullOrEmpty(reference)) return null;
        int n = 0, i = 0;
        for (; i < reference.Length && i < 3 && reference[i] is >= 'A' and <= 'Z'; i++) n = n * 26 + reference[i] - 'A' + 1;
        return i == 0 ? null : n - 1;
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
