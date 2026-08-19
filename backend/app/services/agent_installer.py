"""Generates the per-organization, pre-configured Windows agent installer.

The **portable bundle** (build_offline_bundle_zip) is the only shape: a single .zip with
the framework-dependent Service + Tray builds plus a pre-keyed installer that runs
everything through the trusted `dotnet` host. That indirection is the point — it survives
locked-down corporate machines (ASR blocking unsigned exes, a missing .NET runtime, DNS
that can't reach the backend). Copy it to any number of PCs; the enrollment token is
already baked in and is reusable (enroll() keys devices by machine id and never consumes
the token).

A second, older shape used to exist: a small .ps1 that downloaded a *self-contained* agent
build (~34 MB, the whole .NET runtime inlined) from the backend at install time. It was
removed because the architecture moved to the framework-dependent + trusted-dotnet-host
approach precisely to get past antivirus blocking, the portal never surfaced it, and
shipping that 34 MB blob in every container image cost far more than the path was worth —
on a fleet rollout it would also have pulled ~34 MB per machine over the customer's link.

Placeholders are substituted with str.replace (not str.format) so PowerShell's
own braces need no escaping.
"""
import io
import json
import zipfile
from pathlib import Path

_DOWNLOADS = Path(__file__).resolve().parents[2] / "downloads"
# Framework-dependent Service + Tray builds for the portable bundle.
PORTABLE_ZIP = _DOWNLOADS / "agent-portable.zip"
# Org-agnostic uninstaller (Uninstall-AstraAgent.bat + .ps1), offered as a separate download.
UNINSTALLER_ZIP = _DOWNLOADS / "agent-uninstaller.zip"

# Single-file .exe installer, built by agent/install/Build-Installer.ps1. Unlike the
# zip it is NOT generated per organization: the Inno Setup compiler is Windows-only
# and this backend runs on Linux, so one prebuilt exe is served to everyone and the
# per-org enrollment key travels in the filename it is served under. The sidecar
# records which backend it was compiled against — see setup_exe_path().
SETUP_EXE = _DOWNLOADS / "AstraAgent-Setup.exe"
SETUP_MANIFEST = _DOWNLOADS / "AstraAgent-Setup.json"
# Must match KeyPrefix in agent/install/AstraAgent.iss — that script parses the key
# back out of its own filename, so the two spellings have to agree exactly.
SETUP_EXE_PREFIX = "AstraAgent-Setup-"

# Optional IP the portable installer pins the backend hostname to, for networks whose
# DNS can't resolve it. Empty = no pin, which is correct whenever the backend is on a
# custom domain that resolves publicly. Configure via ASTRA_AGENT_BACKEND_IP only as a
# temporary workaround: a hosts pin overrides DNS, so a stale one blackholes the agent.
DEFAULT_BACKEND_IP = ""


# ── Portable bundle installer: runs via the trusted dotnet host ─────────────────
# Mirrors agent/install/Install-AstraAgent-Portable.ps1, with the token/URL baked in.
# Delimited with ''' because the embedded VBS line contains a triple double-quote.
_PORTABLE_TEMPLATE = r'''#Requires -RunAsAdministrator
<#
    ASTRA Agent — portable installer, pre-configured for your organization.
    Run elevated:  powershell -ExecutionPolicy Bypass -File .\Install-AstraAgent.ps1
    Installs the background Service + tray Chat via the trusted dotnet host so
    antivirus/ASR does not block them. The enrollment token is already baked in.
#>
param(
    [string]$EnrollmentToken = "@@TOKEN@@",
    [string]$ServerUrl       = "@@SERVER_URL@@",
    [string]$BackendIp       = "@@BACKEND_IP@@",
    # Optional outbound proxy for locked-down corporate networks, e.g. http://proxy.corp:8080.
    # Leave empty to auto-detect the corporate proxy (machine config); the agent works direct
    # or through an auto-detected proxy without this.
    [string]$ProxyUrl        = "",
    [string]$ServiceSrc      = "$PSScriptRoot\dist-fd",
    [string]$TraySrc         = "$PSScriptRoot\dist-tray"
)

$ErrorActionPreference = "Stop"
$ServerUrl = $ServerUrl.TrimEnd('/')
$fqdn = ([Uri]$ServerUrl).Host
$svcName = "AstraAgent"
$svcDir  = "$env:ProgramFiles\Astra\Agent"
$trayDir = "$env:ProgramFiles\Astra\Tray"

Write-Host "==== ASTRA agent -> $ServerUrl ====" -ForegroundColor Cyan

function Get-DotnetHost {
    $d = (Get-Command dotnet -ErrorAction SilentlyContinue).Source
    if (-not $d) { $d = "$env:ProgramFiles\dotnet\dotnet.exe" }
    return $d
}
$dotnet = Get-DotnetHost
$haveDesktop8 = $false
if (Test-Path $dotnet) {
    if ((& $dotnet --list-runtimes 2>$null) -match 'Microsoft\.WindowsDesktop\.App 8\.') { $haveDesktop8 = $true }
}
if (-not $haveDesktop8) {
    Write-Host "Installing the .NET 8 Desktop Runtime..." -ForegroundColor Yellow
    $rt = "$env:TEMP\windowsdesktop-runtime-8-win-x64.exe"
    try {
        Invoke-WebRequest -Uri "https://aka.ms/dotnet/8.0/windowsdesktop-runtime-win-x64.exe" -OutFile $rt -UseBasicParsing
        Start-Process -FilePath $rt -ArgumentList "/quiet","/norestart" -Wait
    } catch {
        throw "Could not install the .NET 8 Desktop Runtime. Install it from https://dotnet.microsoft.com/download/dotnet/8.0 then re-run. $($_.Exception.Message)"
    }
    $dotnet = Get-DotnetHost
    if (-not (Test-Path $dotnet)) { throw ".NET runtime install did not complete." }
}

# Only touch the hosts file if the backend is genuinely unreachable. A hosts pin
# OVERRIDES working DNS, so writing one we do not need is actively harmful: if the
# backend's IP later changes, the stale pin blackholes this agent permanently.
function Test-BackendReachable {
    try {
        Invoke-WebRequest -Uri "$ServerUrl/health" -UseBasicParsing -TimeoutSec 10 | Out-Null
        return $true
    } catch {
        # Any HTTP response (401/404/500) still proves the host was reached.
        return [bool]$_.Exception.Response
    }
}

if (Test-BackendReachable) {
    Write-Host "Backend is reachable - no hosts change needed." -ForegroundColor Green
} elseif ($BackendIp) {
    Write-Host "Backend not reachable via DNS - pinning $fqdn -> $BackendIp" -ForegroundColor Yellow
    $hostsFile = "$env:windir\System32\drivers\etc\hosts"
    $written = $false
    foreach ($attempt in 1..3) {
        try {
            # One atomic write. The old code did Set-Content then Add-Content,
            # which races its own just-released file handle.
            $lines = @(Get-Content -LiteralPath $hostsFile -ErrorAction Stop)
            $kept  = @($lines | Where-Object { $_ -notmatch [regex]::Escape($fqdn) })
            $kept += "$BackendIp $fqdn"
            Set-Content -LiteralPath $hostsFile -Value $kept -Encoding ASCII -Force -ErrorAction Stop
            $written = $true
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if ($written) {
        ipconfig /flushdns | Out-Null
        Write-Host "Hosts entry added." -ForegroundColor Green
    } else {
        # Antivirus routinely locks/tamper-protects the hosts file. This is an
        # optimization, never a requirement - do NOT fail the install over it.
        Write-Host "WARNING: could not write the hosts file (locked - usually antivirus)." -ForegroundColor Yellow
        Write-Host "         Continuing anyway. If the agent cannot reach the backend," -ForegroundColor Yellow
        Write-Host "         ask IT to allow $fqdn through DNS and the firewall." -ForegroundColor Yellow
    }
} else {
    Write-Host "WARNING: backend not reachable and no IP to pin. Installing anyway;" -ForegroundColor Yellow
    Write-Host "         the agent retries until $fqdn becomes reachable." -ForegroundColor Yellow
}

# Tear down any previous install properly. `sc delete` unregisters the service but
# does NOT kill its process - and this service is hosted by dotnet.exe, which keeps
# AstraAgent.Service.dll locked. Without waiting for the process to actually exit,
# the Copy-Item below fails with "being used by another process".
if (Get-Service $svcName -ErrorAction SilentlyContinue) {
    Write-Host "Removing the existing $svcName service..."
    Stop-Service $svcName -Force -ErrorAction SilentlyContinue
    $deadline = 20
    while ($deadline-- -gt 0) {
        $s = Get-Service $svcName -ErrorAction SilentlyContinue
        if (-not $s -or $s.Status -eq 'Stopped') { break }
        Start-Sleep -Seconds 1
    }
    $old = Get-CimInstance Win32_Service -Filter "Name='$svcName'" -ErrorAction SilentlyContinue
    if ($old -and $old.ProcessId -and $old.ProcessId -ne 0) {
        Stop-Process -Id $old.ProcessId -Force -ErrorAction SilentlyContinue
    }
    sc.exe delete $svcName | Out-Null
    $deadline = 15
    while ($deadline-- -gt 0) {
        if (-not (Get-Service $svcName -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Seconds 1
    }
    if (Get-Service $svcName -ErrorAction SilentlyContinue) {
        throw "The $svcName service is still registered (marked for deletion). Close services.msc and Task Manager, then re-run. A reboot always clears it."
    }
}

# Kill any orphaned host still holding the agent/tray DLLs.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'AstraAgent\.(Service|Tray)|launch-tray\.vbs' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

# Wipe any previous install first. Copy-Item -Force only OVERWRITES files that exist in
# the new bundle - it never deletes stray files left behind by an older version (e.g. an
# old self-contained build's extra DLLs, from before the framework-dependent switch). A
# leftover file with the same name but a mismatched version can make the .NET host load
# the wrong assembly and crash on start, which Windows then reports only as a generic
# "cannot start service" - so always start from an empty directory.
if (Test-Path $svcDir) {
    Write-Host "Clearing the previous install (avoids stale files from an older version)..."
    Remove-Item "$svcDir\*" -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $svcDir | Out-Null
Copy-Item "$ServiceSrc\*" $svcDir -Recurse -Force
if (-not (Test-Path "$svcDir\AstraAgent.Service.dll")) { throw "AstraAgent.Service.dll missing in $ServiceSrc" }
@{ Astra = @{ ServerUrl = $ServerUrl; EnrollmentToken = $EnrollmentToken; HeartbeatIntervalSeconds = 60; ProxyUrl = $ProxyUrl } } |
    ConvertTo-Json -Depth 5 | Set-Content "$svcDir\appsettings.json" -Encoding UTF8
$svcBin = '"{0}" "{1}"' -f $dotnet, "$svcDir\AstraAgent.Service.dll"
New-Service -Name $svcName -BinaryPathName $svcBin -DisplayName "ASTRA Agent" `
    -Description "ASTRA endpoint agent - telemetry and secure self-healing." -StartupType Automatic | Out-Null
sc.exe failure $svcName reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
Start-Service $svcName
Write-Host "Service installed and started." -ForegroundColor Green

if (Test-Path $trayDir) {
    Remove-Item "$trayDir\*" -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $trayDir | Out-Null
Copy-Item "$TraySrc\*" $trayDir -Recurse -Force
@{ Astra = @{ ServerUrl = $ServerUrl; ProxyUrl = $ProxyUrl } } | ConvertTo-Json -Depth 5 |
    Set-Content "$trayDir\appsettings.json" -Encoding UTF8
$vbs = "$trayDir\launch-tray.vbs"
@"
CreateObject("WScript.Shell").Run """$dotnet"" ""$trayDir\AstraAgent.Tray.dll""", 0, False
"@ | Set-Content $vbs -Encoding ASCII
Set-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "AstraAssistant" -Value ("wscript.exe `"$vbs`"")

# Start the tray in the SIGNED-IN USER'S session, not this installer's.
#
# This script is elevated (#Requires -RunAsAdministrator), and in a managed rollout it is
# usually run by IT's admin account or by Intune as SYSTEM — not by the person using the
# machine. A plain Start-Process here inherits that identity, and the tray then resolves
# per-user paths against the WRONG profile: "clear temporary files" reported freeing
# hundreds of MB while the user's own %TEMP% was untouched, because it had emptied the
# installing admin's. It would also draw its window in a session the user can't see.
#
# A scheduled task with /ru INTERACTIVE runs as whoever is logged on at the console, which
# is the account the tray must act for. Run once, then remove the task — the Run key above
# is what starts it at every subsequent logon.
$trayTask = "AstraTrayFirstRun"
try {
    schtasks /create /tn $trayTask /tr "wscript.exe `"$vbs`"" /sc ONCE /st 00:00 /ru INTERACTIVE /f | Out-Null
    schtasks /run /tn $trayTask | Out-Null
    Start-Sleep -Seconds 2
    schtasks /delete /tn $trayTask /f | Out-Null
    Write-Host "Tray chat installed and started in the signed-in user's session." -ForegroundColor Green
} catch {
    # Nobody logged on (a provisioning-time install), or the task API refused. Not fatal:
    # the Run key starts it correctly at the next sign-in, which is the common case anyway.
    Write-Host "Tray chat installed; it will start at the next sign-in." -ForegroundColor Yellow
}

Start-Sleep -Seconds 4
Get-Service $svcName | Select-Object Name, Status, StartType | Format-Table -AutoSize
Write-Host "Done. This device should appear ONLINE in your ASTRA portal within a minute." -ForegroundColor Green
'''


_PORTABLE_README = """ASTRA Agent - Portable Installer (pre-configured)
=================================================

Copy this whole folder to any Windows PC. The PC enrolls into your ASTRA portal,
sends telemetry, and gets the tray chat. The enrollment token is already baked in.

INSTALL - the easy way
  1. Extract this folder anywhere.
  2. Double-click  Install.bat
  3. Click "Yes" on the one permission prompt.
  That's it. Nothing else to do - it sets everything up and keeps running,
  and it comes back automatically after every restart, for every user.

WHAT IT DOES
  - Installs the .NET 8 Desktop Runtime if missing (official Microsoft, signed).
  - Installs the ASTRA service (auto-start) + tray chat (auto-start at login for all
    users) via the trusted dotnet host, so antivirus/ASR does not block them.

REQUIREMENTS
  The PC must be able to reach @@SERVER_URL@@ over HTTPS (port 443). The installer
  checks this first and tells you if it cannot. If your network blocks it, ask IT to
  allow the hostname through DNS and the firewall - that is the supported fix.

VERIFY
  - The device shows ONLINE in the portal within a minute.
  - An "ASTRA Assistant" tray icon appears (the chat).

Server:  @@SERVER_URL@@
Token expires:  @@EXPIRES@@

NOTE: for a production fleet, code-sign the agent binaries and deploy via your
management tool (Intune/SCCM/GPO) rather than copying this folder by hand.
"""


# Double-clickable launcher: self-elevates (one UAC prompt) then runs the installer
# silently. cmd.exe and powershell.exe are trusted, so ASR does not block this.
_INSTALL_BAT = r"""@echo off
REM ASTRA Agent installer - just double-click this file.
title ASTRA Agent Installer

:: Re-launch elevated if we're not already admin (this is the one permission prompt).
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo Installing the ASTRA agent, please wait...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-AstraAgent.ps1"
set "rc=%errorlevel%"
if not "%rc%"=="0" (
    echo.
    echo Installation failed ^(code %rc%^). Please contact your IT administrator.
    pause
)
"""


def build_portable_install_script(
    *, server_url: str, enrollment_token: str, backend_ip: str = DEFAULT_BACKEND_IP
) -> str:
    return (
        _PORTABLE_TEMPLATE
        .replace("@@SERVER_URL@@", server_url.rstrip("/"))
        .replace("@@TOKEN@@", enrollment_token)
        .replace("@@BACKEND_IP@@", backend_ip)
    )


def setup_exe_path(server_url: str) -> Path:
    """The prebuilt .exe installer, if this deployment can legitimately serve it.

    The backend URL is compiled into the exe, so an exe built for one deployment
    would silently enrol devices into another. Rather than hand that out, refuse it
    and let the caller fall back to the .zip, which is always built to match.
    """
    if not SETUP_EXE.is_file() or not SETUP_MANIFEST.is_file():
        raise FileNotFoundError(
            "The .exe installer is not bundled with this deployment. Build it with "
            "agent/install/Build-Installer.ps1 and commit backend/downloads/."
        )
    try:
        built_for = str(json.loads(SETUP_MANIFEST.read_text())["server_url"]).rstrip("/")
    except (ValueError, KeyError, OSError) as exc:
        raise FileNotFoundError(f"{SETUP_MANIFEST.name} is unreadable: {exc}") from exc

    if built_for != server_url.rstrip("/"):
        raise FileNotFoundError(
            f"The bundled .exe installer points at {built_for}, but this deployment "
            f"is {server_url}. Rebuild it with -ServerUrl {server_url}."
        )
    return SETUP_EXE


def setup_exe_filename(enrollment_key: str) -> str:
    """The name the .exe must be served under, since that is where it reads the key.

    Enrollment keys are secrets.token_urlsafe, so they contain only characters that
    are safe in a filename and in a Content-Disposition header. Anything else would
    be a bug upstream, and the installer would reject it anyway.
    """
    return f"{SETUP_EXE_PREFIX}{enrollment_key}.exe"


def build_offline_bundle_zip(
    *,
    server_url: str,
    enrollment_token: str,
    expires_label: str,
    backend_ip: str = DEFAULT_BACKEND_IP,
) -> bytes:
    """Assemble the portable installer: the framework-dependent Service + Tray
    builds + a pre-keyed installer (token baked in) + README, as one .zip."""
    if not PORTABLE_ZIP.is_file():
        raise FileNotFoundError(
            "Portable agent binaries are not bundled with this deployment "
            "(backend/downloads/agent-portable.zip). Commit it and redeploy."
        )

    url = server_url.rstrip("/")
    script = build_portable_install_script(
        server_url=url, enrollment_token=enrollment_token, backend_ip=backend_ip
    )
    readme = _PORTABLE_README.replace("@@SERVER_URL@@", url).replace("@@EXPIRES@@", expires_label)

    src = zipfile.ZipFile(io.BytesIO(PORTABLE_ZIP.read_bytes()))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in src.namelist():
            zf.writestr(name, src.read(name))
        zf.writestr("Install-AstraAgent.ps1", script)
        zf.writestr("Install.bat", _INSTALL_BAT)
        zf.writestr("README.txt", readme)
    return buffer.getvalue()
