using System.Diagnostics;
using System.Text.Json;
using AstraAgent.GuardHost;

// D5: started by the SAVIO service with "--discover <root>…" to map where sensitive files are.
// Browsers start this exe with an extension origin or a manifest path as the first argument,
// never "--discover". The result (folder paths and counts, no file names, no text) is one JSON
// document on stdout. This process has no network (E4's firewall rules).
if (args.Length > 0 && args[0] == "--discover")
{
    // Security review (3b) H1: as SYSTEM over folders users control, follow no junction a user made.
    SafeOpen.TrustOnlyAdminRedirections();
    try { Process.GetCurrentProcess().PriorityClass = ProcessPriorityClass.Idle; } catch { /* best effort */ }
    // Folders come on stdin, one per line (a PC with many profiles would overflow the 32K
    // command line, security review L2), or as arguments. "--pdf" after it: the org reads PDFs too.
    var pdf = args.Length > 1 && args[1] == "--pdf";
    var rest = args[(pdf ? 2 : 1)..];
    var roots = rest.Length > 0 ? rest : Console.In.ReadToEnd().Split('\n').Select(l => l.Trim()).Where(l => l.Length > 0).ToArray();
    var result = Discovery.Run(roots, TimeSpan.FromMilliseconds(5), pdf: pdf);
    await using var stdout = Console.OpenStandardOutput();
    await JsonSerializer.SerializeAsync(stdout, result,
        new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower });
    return 0;
}

// C3b: started by the SAVIO service with "--scan" for files copied to a USB drive. The request
// (paths, keywords, whether to read PDFs) is JSON on stdin; one total comes back on stdout.
if (args.Length > 0 && args[0] == "--scan")
{
    // Security review (3b) H1: as SYSTEM over folders users control, follow no junction a user made.
    SafeOpen.TrustOnlyAdminRedirections();
    var json = new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };
    var request = JsonSerializer.Deserialize<FileScan.Request>(Console.In.ReadToEnd(), json);
    if (request?.Paths is null) return 2;
    await using var stdout = Console.OpenStandardOutput();
    await JsonSerializer.SerializeAsync(stdout, FileScan.Run(request), json);
    return 0;
}

// Started by Chrome / Edge / Firefox when the SAVIO extension connects. stdin/stdout carry the
// native messaging frames; nothing else may be written to stdout, or the browser drops the
// connection. Errors end the process quietly (exit 1) and the browser starts a fresh one.
try
{
    await NativeHost.RunAsync(Console.OpenStandardInput(), Console.OpenStandardOutput());
    return 0;
}
catch (Exception ex) when (ex is IOException or InvalidDataException)
{
    return 1;
}
