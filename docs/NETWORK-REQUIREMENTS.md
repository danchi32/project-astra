# ASTRA Agent — Network Requirements (for customer IT)

Give this page to the customer's IT/network team. The ASTRA agent is a well-behaved
corporate citizen: it makes only outbound HTTPS connections, uses the corporate proxy
automatically, and never needs any inbound port opened. It does **not** try to bypass
security controls — it works *with* them.

## What to allow (outbound only, port 443/HTTPS)

| Purpose | Destination |
|---|---|
| Enrollment, heartbeat, telemetry, remediation, chat | `https://api.astra.technomateai.com` |
| Signed agent auto-update | `https://github.com` and `https://objects.githubusercontent.com` (GitHub Releases CDN) |
| One-time .NET 8 runtime (only if missing at install) | `https://aka.ms` and `https://dotnet.microsoft.com` / `https://download.visualstudio.microsoft.com` |

- **No inbound ports** are required. The agent only *initiates* connections.
- All traffic is **TLS/HTTPS on 443**.

## Proxies — handled automatically

The agent (both the LocalSystem service and the user tray) resolves the outbound proxy in
this order, so in most environments **nothing needs to be configured**:

1. An explicit proxy provided at install time (`-ProxyUrl http://proxy.corp:8080`).
2. The `HTTPS_PROXY` / `HTTP_PROXY` environment variables.
3. The machine-level WinHTTP proxy (`netsh winhttp show proxy`).
4. Direct connection.

Integrated (NTLM/Negotiate) proxy authentication is used, so an authenticating proxy
accepts the machine/service account without any stored password.

**If your network uses a static proxy**, either:
- set it machine-wide once: `netsh winhttp set proxy proxy.corp:8080`, **or**
- install with it: `Install-AstraAgent.ps1 -ProxyUrl http://proxy.corp:8080`.

**WPAD/PAC-only networks** (auto-config with no machine proxy set): provide the proxy
explicitly via `-ProxyUrl`, or allowlist the destinations above so the agent can go direct.

## TLS inspection

If your proxy performs SSL/TLS inspection with your own internal root CA, no change is
needed: the agent validates against the **Windows machine certificate store**, which already
trusts your root CA. The agent does **not** pin certificates, so inspection does not break it.

## Endpoint protection (EDR / antivirus / ASR)

The agent runs its .NET code through the trusted Microsoft `dotnet` host (not an unsigned
custom EXE), so Attack-Surface-Reduction and reputation checks do not block it. If your EDR
still quarantines it, allowlist the install paths:

- `C:\Program Files\Astra\Agent\`
- `C:\Program Files\Astra\Tray\`

## Quick connectivity test (run on a target machine)

```powershell
Invoke-WebRequest "https://api.astra.technomateai.com/health" -UseBasicParsing
# Expect: {"status":"ok",...}. If this fails, the machine cannot reach the backend —
# check the proxy/firewall against the table above.
netsh winhttp show proxy   # shows the machine proxy the service will use
```
