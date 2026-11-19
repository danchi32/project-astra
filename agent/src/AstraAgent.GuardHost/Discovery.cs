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
/// <item>Only text-like files, Word / Excel (.docx / .xlsx) and, if the org chose, PDF; up to
/// 20 MB each (<see cref="Documents"/>).</item>
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
    static readonly HashSet<string> SkipDirs = new(StringComparer.OrdinalIgnoreCase)
        { "AppData", "node_modules", "$Recycle.Bin", "bin", "obj", "packages", "site-packages" };

    // Cloud-only placeholders: FILE_ATTRIBUTE_RECALL_ON_OPEN / RECALL_ON_DATA_ACCESS, and Offline.
    const FileAttributes Skip = FileAttributes.Hidden | FileAttributes.System | FileAttributes.ReparsePoint |
                                FileAttributes.Offline | (FileAttributes)0x40000 | (FileAttributes)0x400000;

    public sealed record Folder(string Path, int Files, int FilesWithFindings, Dictionary<string, int> Counts, int ContactLists);

    public sealed record Result(bool Ok, int FilesScanned, int FilesSkipped, bool Truncated, IReadOnlyList<Folder> Folders);

    /// <param name="pdf">Also read PDFs: the org's choice (<c>--pdf</c>).</param>
    public static Result Run(IEnumerable<string> roots, TimeSpan pause, CancellationToken ct = default, bool pdf = false)
    {
        var folders = new Dictionary<string, Folder>(StringComparer.OrdinalIgnoreCase);
        int scanned = 0, skipped = 0;
        bool truncated = false;
        var options = new EnumerationOptions { IgnoreInaccessible = true, AttributesToSkip = Skip, RecurseSubdirectories = false };

        // Each folder remembers the root it was found under, so its path can be reported as the
        // root plus a cleaned-up remainder (see Report).
        var pending = new Stack<(string Dir, string Root)>(roots.Where(Directory.Exists).Select(r => (r, r)));
        while (pending.Count > 0 && !ct.IsCancellationRequested)
        {
            var (dir, root) = pending.Pop();
            // Security review M1: checked again right before it is opened, roots included. A
            // junction or symlink (to another folder, a system path or a network share) planted
            // by a user is never followed, even if it was swapped in after the folder was listed.
            try
            {
                var info = new DirectoryInfo(dir);
                if (info.Attributes.HasFlag(FileAttributes.ReparsePoint) || info.LinkTarget is not null) continue;
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }
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
                if (!name.StartsWith('.') && !SkipDirs.Contains(name)) pending.Push((sub, root));
            }
            foreach (var file in files)
            {
                if (scanned >= MaxFiles) { truncated = true; pending.Clear(); break; }
                var ext = Path.GetExtension(file);
                if (!TextExt.Contains(ext) && !Documents.Readable(ext, pdf)) continue;
                string? text;
                try { text = Text(file, ext, pdf); }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidDataException) { text = null; }
                if (text is null) { skipped++; continue; }
                scanned++;

                var r = PiiScanner.Scan(text);
                var f = folders.GetValueOrDefault(dir) ?? new Folder(Report(dir, root), 0, 0, new Dictionary<string, int>(), 0);
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

    /// <summary>
    /// The folder's path as it leaves the scanner. Folder names are free text a person chose,
    /// and can carry the very data being looked for ("Clients\\Rahul 2345 6789 0123"), so the part
    /// below the root goes through the same redaction as a paste (security review M3).
    /// </summary>
    internal static string Report(string dir, string root)
    {
        if (dir.Length <= root.Length) return root;
        var below = dir[root.Length..];
        return root + (PiiScanner.Redact(below) ?? "\\[folder]");
    }

    /// <summary>A file whose text this scanner reads (text-like, Word / Excel, PDF if chosen).</summary>
    internal static bool Checkable(string ext, bool pdf) => TextExt.Contains(ext) || Documents.Readable(ext, pdf);

    /// <summary>The text of one file, or null if it is too big or not what its name says.</summary>
    internal static string? Text(string path, string ext, bool pdf = false)
    {
        if (new FileInfo(path).Length > MaxFileBytes) return null;
        if (TextExt.Contains(ext)) return Documents.Cap(File.ReadAllText(path));
        return Documents.Text(File.ReadAllBytes(path), ext, pdf);
    }
}
