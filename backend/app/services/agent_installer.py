"""Generates per-organization, pre-configured Windows agent installers.

Two shapes, both minting a reusable enrollment token (one token can enroll any
number of machines — enroll() keys devices by machine id and never consumes the
token):

- Online installer  (build_install_script): a small .ps1 that downloads the agent
  from the backend at install time. Good for one or a few unmanaged machines.
- Portable bundle    (build_portable_bundle_zip): a single .zip with the framework-
  dependent Service + Tray builds, plus a pre-keyed installer that runs everything
  through the trusted `dotnet` host. Handles locked-down corporate machines
  (ASR unsigned-exe block, missing .NET runtime, DNS that can't reach the backend).
  Copy to any number of PCs; the enrollment token is already baked in.

Placeholders are substituted with str.replace (not str.format) so PowerShell's
own braces need no escaping.
"""
import io
import zipfile
from pathlib import Path

_DOWNLOADS = Path(__file__).resolve().parents[2] / "downloads"
# Self-contained single build served to the online self-download installer.
AGENT_ZIP = _DOWNLOADS / "agent.zip"
# Framework-dependent Service + Tray builds for the portable bundle.
PORTABLE_ZIP = _DOWNLOADS / "agent-portable.zip"
# Org-agnostic uninstaller (Uninstall-AstraAgent.bat + .ps1), offered as a separate download.
UNINSTALLER_ZIP = _DOWNLOADS / "agent-uninstaller.zip"

# Optional IP the portable installer pins the backend hostname to, for networks whose
# DNS can't resolve it. Empty = no pin, which is correct whenever the backend is on a
# custom domain that resolves publicly. Configure via ASTRA_AGENT_BACKEND_IP only as a
# temporary workaround: a hosts pin overrides DNS, so a stale one blackholes the agent.
DEFAULT_BACKEND_IP = ""


# ── Online installer: downloads the agent from the backend at install time ──────
_INSTALL_TEMPLATE = r"""#Requires -RunAsAdministrator
<#
    ASTRA Windows Agent installer  —  pre-configured for your organization.

    Right-click this file -> "Run with PowerShell" (approve the admin prompt), or:
        powershell -ExecutionPolicy Bypass -File .\Install-AstraAgent.ps1

    Downloads the agent from your ASTRA server, installs it as a Windows service,
    and enrolls this machine automatically.
#>
param(
    [string]$ServerUrl       = "@@SERVER_URL@@",
    [string]$EnrollmentToken = "@@TOKEN@@",
    [string]$ProxyUrl        = "",
    [string]$InstallDir      = "$env:ProgramFiles\Astra\Agent"
)

$ErrorActionPreference = "Stop"
$ServiceName = "AstraAgent"
$Exe         = "AstraAgent.Service.exe"

if ([string]::IsNullOrWhiteSpace($ServerUrl))       { throw "ServerUrl is required." }
if ([string]::IsNullOrWhiteSpace($EnrollmentToken)) { throw "EnrollmentToken is required." }
$ServerUrl = $ServerUrl.TrimEnd('/')

Write-Host "ASTRA agent -> $ServerUrl" -ForegroundColor Cyan

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$zipPath = Join-Path $env:TEMP "astra-agent.zip"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    Invoke-WebRequest -Uri "$ServerUrl/api/v1/downloads/agent" -OutFile $zipPath -UseBasicParsing
} catch {
    throw "Could not download the agent from $ServerUrl. $($_.Exception.Message)"
}
Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

$exePath = Join-Path $InstallDir $Exe
if (-not (Test-Path $exePath)) { throw "Expected $Exe in $InstallDir." }

@{ Astra = @{ ServerUrl = $ServerUrl; EnrollmentToken = $EnrollmentToken; HeartbeatIntervalSeconds = 60; ProxyUrl = $ProxyUrl } } |
    ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $InstallDir "appsettings.json") -Encoding UTF8

sc.exe create $ServiceName binPath= "`"$exePath`"" start= auto | Out-Null
sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
Start-Service -Name $ServiceName
Write-Host "ASTRA agent installed and started." -ForegroundColor Green
"""


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

New-Item -ItemType Directory -Force -Path $trayDir | Out-Null
Copy-Item "$TraySrc\*" $trayDir -Recurse -Force
@{ Astra = @{ ServerUrl = $ServerUrl; ProxyUrl = $ProxyUrl } } | ConvertTo-Json -Depth 5 |
    Set-Content "$trayDir\appsettings.json" -Encoding UTF8
$vbs = "$trayDir\launch-tray.vbs"
@"
CreateObject("WScript.Shell").Run """$dotnet"" ""$trayDir\AstraAgent.Tray.dll""", 0, False
"@ | Set-Content $vbs -Encoding ASCII
Set-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "AstraAssistant" -Value ("wscript.exe `"$vbs`"")
Start-Process wscript.exe -ArgumentList "`"$vbs`""
Write-Host "Tray chat installed and launched." -ForegroundColor Green

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


def build_install_script(*, server_url: str, enrollment_token: str) -> str:
    return (
        _INSTALL_TEMPLATE
        .replace("@@SERVER_URL@@", server_url.rstrip("/"))
        .replace("@@TOKEN@@", enrollment_token)
    )


def build_portable_install_script(
    *, server_url: str, enrollment_token: str, backend_ip: str = DEFAULT_BACKEND_IP
) -> str:
    return (
        _PORTABLE_TEMPLATE
        .replace("@@SERVER_URL@@", server_url.rstrip("/"))
        .replace("@@TOKEN@@", enrollment_token)
        .replace("@@BACKEND_IP@@", backend_ip)
    )


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
