using System;
using System.Net;
using System.Net.Http;
using System.Runtime.InteropServices;

namespace AstraAgent.Service.Net;

/// <summary>Builds an <see cref="HttpMessageHandler"/> that reaches the backend through whatever
/// proxy a corporate network mandates — automatically, for every organization, with no per-site
/// setup.
///
/// This matters most for the Windows Service, which runs as LocalSystem: the managed default
/// proxy reads the *interactive user's* WinINET settings and sees nothing under SYSTEM, so a
/// proxied corporate network would silently black-hole every heartbeat/enroll. We resolve the
/// proxy in order of precedence:
///   1. an explicit proxy URL (IT-provided, in appsettings) — always wins;
///   2. the standard HTTPS_PROXY / HTTP_PROXY environment variables (common on corporate images);
///   3. the machine-level WinHTTP proxy (`netsh winhttp set proxy`), which a LocalSystem service
///      can actually see — read directly from the Windows HTTP stack;
///   4. the system default proxy / direct.
/// Integrated (NTLM/Negotiate) proxy authentication is enabled so an authenticating corporate
/// proxy accepts the running account without a stored password. We never pin the API's TLS
/// certificate, so corporate TLS-inspection proxies (their own root CA in the machine trust
/// store) keep working. For WPAD/PAC-only networks with no machine proxy, IT sets Astra:ProxyUrl.</summary>
public static class ProxyHttp
{
    public static HttpMessageHandler CreateHandler(string? explicitProxyUrl)
    {
        var handler = new HttpClientHandler
        {
            UseProxy = true,
            DefaultProxyCredentials = CredentialCache.DefaultCredentials,
        };

        // 1 + 2. Explicit proxy (appsettings) or the standard proxy environment variables.
        var configured = FirstNonEmpty(
            explicitProxyUrl,
            Environment.GetEnvironmentVariable("HTTPS_PROXY"),
            Environment.GetEnvironmentVariable("https_proxy"),
            Environment.GetEnvironmentVariable("HTTP_PROXY"),
            Environment.GetEnvironmentVariable("http_proxy"));
        var explicitProxy = ToProxy(configured);
        if (explicitProxy is not null)
        {
            handler.Proxy = explicitProxy;
            return handler;
        }

        // 3. The machine-level WinHTTP proxy — the one a LocalSystem service can see.
        var machineProxy = TryGetMachineWinHttpProxy();
        if (machineProxy is not null)
        {
            handler.Proxy = machineProxy;
            return handler;
        }

        // 4. Otherwise leave Proxy unset -> system default / direct.
        return handler;
    }

    private static WebProxy? ToProxy(string? value)
    {
        if (string.IsNullOrWhiteSpace(value)) return null;
        var v = ExtractHttpsEntry(value.Trim());
        if (string.IsNullOrWhiteSpace(v)) return null;
        if (!v.Contains("://")) v = "http://" + v;   // WinHTTP strings omit the scheme
        return Uri.TryCreate(v, UriKind.Absolute, out var uri)
            ? new WebProxy(uri) { UseDefaultCredentials = true }
            : null;
    }

    // A WinHTTP proxy string can be a bare "host:port" or per-scheme "http=h:p;https=h2:p2".
    // Prefer the https entry; otherwise take the first host:port token.
    private static string ExtractHttpsEntry(string s)
    {
        if (!s.Contains('=')) return s;
        var parts = s.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        foreach (var part in parts)
        {
            var kv = part.Split('=', 2);
            if (kv.Length == 2 && kv[0].Trim().Equals("https", StringComparison.OrdinalIgnoreCase))
                return kv[1].Trim();
        }
        foreach (var part in parts)
        {
            var kv = part.Split('=', 2);
            return (kv.Length == 2 ? kv[1] : kv[0]).Trim();
        }
        return s;
    }

    private static WebProxy? TryGetMachineWinHttpProxy()
    {
        var info = new WINHTTP_PROXY_INFO();
        try
        {
            if (!WinHttpGetDefaultProxyConfiguration(ref info))
                return null;
            // 3 == WINHTTP_ACCESS_TYPE_NAMED_PROXY
            if (info.dwAccessType != 3 || info.lpszProxy == IntPtr.Zero)
                return null;
            return ToProxy(Marshal.PtrToStringUni(info.lpszProxy));
        }
        catch
        {
            return null;
        }
        finally
        {
            if (info.lpszProxy != IntPtr.Zero) GlobalFree(info.lpszProxy);
            if (info.lpszProxyBypass != IntPtr.Zero) GlobalFree(info.lpszProxyBypass);
        }
    }

    private static string? FirstNonEmpty(params string?[] values)
    {
        foreach (var v in values)
            if (!string.IsNullOrWhiteSpace(v)) return v;
        return null;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct WINHTTP_PROXY_INFO
    {
        public uint dwAccessType;
        public IntPtr lpszProxy;
        public IntPtr lpszProxyBypass;
    }

    [DllImport("winhttp.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool WinHttpGetDefaultProxyConfiguration(ref WINHTTP_PROXY_INFO info);

    [DllImport("kernel32.dll")]
    private static extern IntPtr GlobalFree(IntPtr hMem);
}
