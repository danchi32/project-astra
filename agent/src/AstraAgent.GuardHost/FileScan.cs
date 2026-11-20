using AstraAgent.Guard;

namespace AstraAgent.GuardHost;

/// <summary>
/// Phase 3c · C3b: what a set of files holds, in counts, for files copied to a USB drive.
///
/// Runs inside the native host (<c>savio-guard-host.exe --scan</c>), the process E4 keeps off the
/// network, like the weekly file map. The service names the files on stdin; what comes back is
/// one total: how many were read, how many could not be, counts per kind, whether any was a
/// contact list, how many restricted keywords. No file names, no text.
/// </summary>
public static class FileScan
{
    public const int MaxFiles = 200;

    /// <summary>Files that hold text but are not read here: old Office, PowerPoint, archives, and
    /// PDFs where the org did not choose to read them. Copying one is "could not check".</summary>
    static readonly HashSet<string> Opaque = new(StringComparer.OrdinalIgnoreCase)
        { ".doc", ".xls", ".xlsm", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf", ".zip", ".rar", ".7z", ".pdf" };

    public sealed record Request(IReadOnlyList<string> Paths, IReadOnlyList<string>? Keywords = null, bool Pdf = false);

    public sealed record Result(int Files, int Unreadable, Dictionary<string, int> Counts, bool ContactList, int KeywordHits);

    public static Result Run(Request r)
    {
        int files = 0, unreadable = 0;
        var counts = new Dictionary<string, int>();
        var contact = false;
        var keywords = new HashSet<int>();
        foreach (var path in r.Paths.Take(MaxFiles))
        {
            var ext = Path.GetExtension(path);
            if (!Discovery.Checkable(ext, r.Pdf))
            {
                if (Opaque.Contains(ext)) unreadable++;   // a photo or a program is not a document
                continue;
            }
            string? text;
            try { text = Read(path, ext, r.Pdf); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidDataException) { text = null; }
            if (text is null) { unreadable++; continue; }
            files++;
            var s = PiiScanner.Scan(text, r.Keywords);
            foreach (var (kind, n) in s.Counts.Where(kv => kv.Value > 0))
                counts[kind.ToString()] = counts.GetValueOrDefault(kind.ToString()) + n;
            contact |= s.ContactList;
            keywords.UnionWith(s.KeywordHits);
        }
        return new Result(files, unreadable, counts, contact, keywords.Count);
    }

    /// <summary>A copied file's text, opened only if no link leads to it and it is really on its
    /// drive (security review 3b H1: this runs as SYSTEM on paths a user controls).</summary>
    static string? Read(string path, string ext, bool pdf)
    {
        var root = Path.GetPathRoot(Path.GetFullPath(path));
        if (string.IsNullOrEmpty(root)) return null;
        var bytes = SafeOpen.ReadUnder(root, path, Discovery.MaxFileBytes);
        return bytes is null ? null : Discovery.TextOf(bytes, ext, pdf);
    }
}
