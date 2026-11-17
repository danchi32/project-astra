using System.IO.Compression;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using AstraAgent.Guard;

namespace AstraAgent.GuardHost;

/// <summary>
/// Phase 3 · D5: where sensitive data lives on this PC, by folder, in counts.
///
/// Runs inside the native host (<c>savio-guard-host.exe --discover &lt;root&gt;…</c>), the one
/// process E4 cuts off from the network. File contents are read and scanned here and nowhere
/// else. What leaves is one line per folder that had findings: its path, how many files were
/// read, how many had findings, and counts per kind. No file names, no text.
///
/// Careful by design:
/// <list type="bullet">
/// <item>Only text-like files and Word / Excel (.docx / .xlsx), up to 20 MB each.</item>
/// <item>Cloud-only files (OneDrive placeholders) are skipped: reading one would download it.</item>
/// <item>Hidden, system and linked (junction) entries are skipped, and so are AppData, dot-folders
/// and dependency folders.</item>
/// <item>At most 50,000 files a run, at idle priority, pausing between files.</item>
/// </list>
/// </summary>
public static class Discovery
{
    public const long MaxFileBytes = 20 * 1024 * 1024;
    public const int MaxFiles = 50_000;
    public const int MaxFolders = 500;

    static readonly HashSet<string> TextExt = new(StringComparer.OrdinalIgnoreCase)
        { ".txt", ".csv", ".tsv", ".json", ".md", ".xml", ".log", ".html", ".htm" };
    static readonly HashSet<string> OfficeExt = new(StringComparer.OrdinalIgnoreCase) { ".docx", ".xlsx" };
    static readonly HashSet<string> SkipDirs = new(StringComparer.OrdinalIgnoreCase)
        { "AppData", "node_modules", "$Recycle.Bin", "bin", "obj", "packages", "site-packages" };

    // Cloud-only placeholders: FILE_ATTRIBUTE_RECALL_ON_OPEN / RECALL_ON_DATA_ACCESS, and Offline.
    const FileAttributes Skip = FileAttributes.Hidden | FileAttributes.System | FileAttributes.ReparsePoint |
                                FileAttributes.Offline | (FileAttributes)0x40000 | (FileAttributes)0x400000;

    public sealed record Folder(string Path, int Files, int FilesWithFindings, Dictionary<string, int> Counts, int ContactLists);

    public sealed record Result(bool Ok, int FilesScanned, int FilesSkipped, bool Truncated, IReadOnlyList<Folder> Folders);

    public static Result Run(IEnumerable<string> roots, TimeSpan pause, CancellationToken ct = default)
    {
        var folders = new Dictionary<string, Folder>(StringComparer.OrdinalIgnoreCase);
        int scanned = 0, skipped = 0;
        bool truncated = false;
        var options = new EnumerationOptions { IgnoreInaccessible = true, AttributesToSkip = Skip, RecurseSubdirectories = false };

        var pending = new Stack<string>(roots.Where(Directory.Exists));
        while (pending.Count > 0 && !ct.IsCancellationRequested)
        {
            var dir = pending.Pop();
            IEnumerable<string> subdirs, files;
            try
            {
                subdirs = Directory.EnumerateDirectories(dir, "*", options).ToList();
                files = Directory.EnumerateFiles(dir, "*", options).ToList();
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var sub in subdirs)
            {
                var name = Path.GetFileName(sub);
                if (!name.StartsWith('.') && !SkipDirs.Contains(name)) pending.Push(sub);
            }
            foreach (var file in files)
            {
                if (scanned >= MaxFiles) { truncated = true; pending.Clear(); break; }
                var ext = Path.GetExtension(file);
                if (!TextExt.Contains(ext) && !OfficeExt.Contains(ext)) continue;
                string? text;
                try { text = Text(file, ext); }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidDataException) { text = null; }
                if (text is null) { skipped++; continue; }
                scanned++;

                var r = PiiScanner.Scan(text);
                var f = folders.GetValueOrDefault(dir) ?? new Folder(dir, 0, 0, new Dictionary<string, int>(), 0);
                f = f with { Files = f.Files + 1 };
                if (r.Any)
                {
                    foreach (var (kind, n) in r.Counts.Where(kv => kv.Value > 0))
                        f.Counts[kind.ToString()] = f.Counts.GetValueOrDefault(kind.ToString()) + n;
                    f = f with { FilesWithFindings = f.FilesWithFindings + 1, ContactLists = f.ContactLists + (r.ContactList ? 1 : 0) };
                }
                folders[dir] = f;
                if (pause > TimeSpan.Zero) Thread.Sleep(pause);
            }
        }

        var found = folders.Values.Where(f => f.FilesWithFindings > 0)
            .OrderByDescending(f => f.FilesWithFindings).ThenBy(f => f.Path, StringComparer.OrdinalIgnoreCase).ToList();
        return new Result(true, scanned, skipped, truncated || found.Count > MaxFolders, found.Take(MaxFolders).ToList());
    }

    /// <summary>The text of one file, or null if it is too big or not what its name says.</summary>
    internal static string? Text(string path, string ext)
    {
        if (new FileInfo(path).Length > MaxFileBytes) return null;
        if (TextExt.Contains(ext)) return Cap(File.ReadAllText(path));

        using var zip = ZipFile.OpenRead(path);
        var parts = ext.Equals(".docx", StringComparison.OrdinalIgnoreCase)
            ? zip.Entries.Where(e => e.FullName == "word/document.xml")
            : zip.Entries.Where(e => e.FullName == "xl/sharedStrings.xml" ||
                                     (e.FullName.StartsWith("xl/worksheets/sheet") && e.FullName.EndsWith(".xml")));
        var sb = new StringBuilder();
        foreach (var entry in parts)
        {
            // A zip bomb is refused by its declared size before anything is inflated.
            if (entry.Length > MaxFileBytes || sb.Length > PiiScanner.MaxChars) return null;
            using var reader = new StreamReader(entry.Open());
            sb.Append(XmlText(reader.ReadToEnd())).Append('\n');
        }
        return Cap(sb.ToString());
    }

    static readonly Regex LineEnd = new(@"</(w:p|row|si)>", RegexOptions.Compiled);
    static readonly Regex CellEnd = new(@"</c>", RegexOptions.Compiled);
    static readonly Regex Tag = new(@"<[^>]{0,2000}>", RegexOptions.Compiled);

    /// <summary>Word paragraphs and Excel rows become lines, cells become tabs, tags go.</summary>
    static string XmlText(string xml) =>
        WebUtility.HtmlDecode(Tag.Replace(CellEnd.Replace(LineEnd.Replace(xml, "\n"), "\t"), ""));

    static string Cap(string s) => s.Length > PiiScanner.MaxChars ? s[..PiiScanner.MaxChars] : s;
}
