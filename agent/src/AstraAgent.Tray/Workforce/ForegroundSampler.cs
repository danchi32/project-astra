using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Automation;

namespace AstraAgent.Tray.Workforce;

/// <summary>Reads what the person is looking at right now: the foreground window's app and,
/// for a browser, the website domain.
///
/// User-session only — this is exactly why it lives in the Tray and not the LocalSystem
/// Service: a process in session 0 cannot see a user's foreground window, and UI Automation
/// against a browser's address bar has to run inside the interactive session.
///
/// Privacy is built in: only the DOMAIN is ever returned, never a path or query string (that
/// is where tokens and private parameters live — plan §6). The URL read is best-effort; any
/// failure degrades to app-only, never throws, and incognito/hardened browsers that hide the
/// address bar simply yield no domain.</summary>
public static class ForegroundSampler
{
    public sealed record Sample(string App, string? Domain, string? Path);

    private static readonly string[] Browsers =
        ["chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "chromium", "iexplore"];

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    /// <summary>The current foreground app + domain (and, in "path" URL mode, the
    /// query-stripped path), or null when there is nothing attributable (no foreground window,
    /// the lock screen, or a window we cannot read).</summary>
    public static Sample? Capture(string urlMode = "domain")
    {
        try
        {
            var hwnd = GetForegroundWindow();
            if (hwnd == IntPtr.Zero)
                return null;

            GetWindowThreadProcessId(hwnd, out var pid);
            if (pid == 0)
                return null;

            string process;
            try
            {
                using var p = Process.GetProcessById((int)pid);
                process = p.ProcessName;   // e.g. "Code", "chrome", "WINWORD"
            }
            catch
            {
                return null;   // process gone or not readable (elevated) — skip this sample
            }
            if (string.IsNullOrWhiteSpace(process))
                return null;

            string? domain = null;
            string? path = null;
            if (IsBrowser(process))
            {
                // One parse yields both host and query-stripped path (the query/fragment are
                // never included — Uri.AbsolutePath drops them).
                var (host, urlPath) = ParseSite(TryReadBrowserUrl(hwnd));
                domain = host;
                if (urlMode == "path")
                    path = urlPath;
            }

            return new Sample(process, domain, path);
        }
        catch
        {
            return null;   // never let a sample crash the collector
        }
    }

    public static bool IsBrowser(string processName)
    {
        var p = processName.Trim().ToLowerInvariant();
        foreach (var b in Browsers)
            if (p == b)
                return true;
        return false;
    }

    /// <summary>Parse a browser URL once into (host, query-stripped path). `Uri.Host` and
    /// `Uri.AbsolutePath` both exclude the query and fragment, which is the privacy guarantee —
    /// a query can never leak through here. The host is lower-cased with "www." stripped; the
    /// path is null for a bare site root. DomainFromUrl/PathFromUrl are thin views of this, so
    /// there is one implementation and the two values are always parsed from the same URL.</summary>
    public static (string? Domain, string? Path) ParseSite(string? url)
    {
        if (string.IsNullOrWhiteSpace(url))
            return (null, null);
        var u = url.Trim();
        // The address bar often shows no scheme ("github.com/foo"); give Uri one to parse.
        if (!u.Contains("://"))
            u = "http://" + u;
        if (!Uri.TryCreate(u, UriKind.Absolute, out var uri) || string.IsNullOrEmpty(uri.Host))
            return (null, null);

        var host = uri.Host.ToLowerInvariant();
        if (host.StartsWith("www."))
            host = host[4..];

        var path = uri.AbsolutePath;
        string? cleanPath = string.IsNullOrEmpty(path) || path == "/"
            ? null
            : (path.Length > 400 ? path[..400] : path);
        return (host, cleanPath);
    }

    public static string? DomainFromUrl(string? url) => ParseSite(url).Domain;

    public static string? PathFromUrl(string? url) => ParseSite(url).Path;

    // ── UI Automation ─────────────────────────────────────────────────────────
    // Reads the foreground browser's address bar via the managed UI Automation client.
    // Best-effort: any failure (address bar hidden in incognito/kiosk, UIA blocked, a browser
    // whose tree differs) returns null and the sample is app-only, never an error.

    private static string? TryReadBrowserUrl(IntPtr hwnd)
    {
        try
        {
            var root = AutomationElement.FromHandle(hwnd);
            if (root is null)
                return null;

            // Pass 1 — the active tab's web Document. Every open tab is a Document control whose
            // value is its URL; the active one's Name is the page title, which is also the
            // window title. Matching on that picks the active tab out of all of them. This is
            // what makes Firefox work (its address-bar Edit exposes no value) AND is better for
            // Chrome/Edge too — it reads the LOADED url, not half-typed text in the address bar.
            var title = WindowTitle(hwnd);
            var docs = root.FindAll(
                TreeScope.Descendants,
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Document));
            string? best = null;
            int bestLen = -1;
            foreach (AutomationElement doc in docs)
            {
                var info = doc.Current;
                var name = info.Name ?? "";
                // Skip background tabs: their documents are off-screen, so a tab that merely
                // shares (or is a substring of) the window title can't be mistaken for the
                // active one. The active tab's document is on-screen and its name is the title.
                if (name.Length == 0 || name.Length <= bestLen || info.IsOffscreen
                    || !title.Contains(name, StringComparison.Ordinal))
                    continue;
                var value = ReadValue(doc);
                if (!string.IsNullOrWhiteSpace(value) &&
                    (value.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
                     value.StartsWith("https://", StringComparison.OrdinalIgnoreCase)))
                {
                    best = value;
                    bestLen = name.Length;
                }
            }
            if (best is not null)
                return best;

            // Pass 2 — the address-bar Edit (Chromium internal pages with no document title, or
            // a browser whose document tree differs). Matched by the bar's accessible name.
            var edits = root.FindAll(
                TreeScope.Descendants,
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Edit));
            foreach (AutomationElement element in edits)
            {
                var name = element.Current.Name ?? "";
                if (name.IndexOf("address", StringComparison.OrdinalIgnoreCase) < 0 &&
                    name.IndexOf("url", StringComparison.OrdinalIgnoreCase) < 0 &&
                    name.IndexOf("enter address", StringComparison.OrdinalIgnoreCase) < 0)
                    continue;
                var value = ReadValue(element);
                if (!string.IsNullOrWhiteSpace(value))
                    return value;
            }
        }
        catch
        {
            // Address bar hidden (incognito/kiosk), UIA blocked, or a browser whose tree
            // differs — app-only is a fine answer.
        }
        return null;
    }

    private static string WindowTitle(IntPtr hwnd)
    {
        var sb = new StringBuilder(512);
        _ = GetWindowText(hwnd, sb, sb.Capacity);
        return sb.ToString();
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);

    private static string? ReadValue(AutomationElement element)
    {
        try
        {
            if (element.TryGetCurrentPattern(ValuePattern.Pattern, out var pattern) &&
                pattern is ValuePattern value &&
                !string.IsNullOrWhiteSpace(value.Current.Value))
                return value.Current.Value;
        }
        catch
        {
            // An element can disappear between the find and the read — skip it.
        }
        return null;
    }
}
