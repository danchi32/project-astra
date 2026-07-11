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

# Default IP the portable installer pins the backend hostname to, for corporate
# networks whose DNS can't resolve it. Overridable per download.
DEFAULT_BACKEND_IP = "69.46.46.120"


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

@{ Astra = @{ ServerUrl = $ServerUrl; EnrollmentToken = $EnrollmentToken; HeartbeatIntervalSeconds = 60 } } |
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

if ($BackendIp) {
    $resolves = $false
    try { $resolves = [bool](Resolve-DnsName $fqdn -ErrorAction Stop) } catch { $resolves = $false }
    if (-not $resolves) {
        Write-Host "Adding hosts entry $fqdn -> $BackendIp" -ForegroundColor Yellow
        $hostsFile = "$env:windir\System32\drivers\etc\hosts"
        (Get-Content $hostsFile) -notmatch ([regex]::Escape($fqdn)) | Set-Content $hostsFile
        Add-Content $hostsFile "$BackendIp $fqdn"
        ipconfig /flushdns | Out-Null
    }
}

if (Get-Service $svcName -ErrorAction SilentlyContinue) {
    Stop-Service $svcName -Force -ErrorAction SilentlyContinue
    sc.exe delete $svcName | Out-Null
    Start-Sleep -Seconds 2
}
New-Item -ItemType Directory -Force -Path $svcDir | Out-Null
Copy-Item "$ServiceSrc\*" $svcDir -Recurse -Force
if (-not (Test-Path "$svcDir\AstraAgent.Service.dll")) { throw "AstraAgent.Service.dll missing in $ServiceSrc" }
@{ Astra = @{ ServerUrl = $ServerUrl; EnrollmentToken = $EnrollmentToken; HeartbeatIntervalSeconds = 60 } } |
    ConvertTo-Json -Depth 5 | Set-Content "$svcDir\appsettings.json" -Encoding UTF8
$svcBin = '"{0}" "{1}"' -f $dotnet, "$svcDir\AstraAgent.Service.dll"
New-Service -Name $svcName -BinaryPathName $svcBin -DisplayName "ASTRA Agent" `
    -Description "ASTRA endpoint agent - telemetry and secure self-healing." -StartupType Automatic | Out-Null
sc.exe failure $svcName reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
Start-Service $svcName
Write-Host "Service installed and started." -ForegroundColor Green

New-Item -ItemType Directory -Force -Path $trayDir | Out-Null
Copy-Item "$TraySrc\*" $trayDir -Recurse -Force
@{ Astra = @{ ServerUrl = $ServerUrl } } | ConvertTo-Json -Depth 5 |
    Set-Content "$trayDir\appsettings.json" -Encoding UTF8
$vbs = "$trayDir\launch-tray.vbs"
@"
CreateObject("WScript.Shell").Run """$dotnet"" ""$trayDir\AstraAgent.Tray.dll""", 0, False
"@ | Set-Content $vbs -Encoding ASCII
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "AstraAssistant" -Value ("wscript.exe `"$vbs`"")
Start-Process wscript.exe -ArgumentList "`"$vbs`""
Write-Host "Tray chat installed and launched." -ForegroundColor Green

Start-Sleep -Seconds 4
Get-Service $svcName | Select-Object Name, Status, StartType | Format-Table -AutoSize
Write-Host "Done. This device should appear ONLINE in your ASTRA portal within a minute." -ForegroundColor Green
'''


_PORTABLE_README = """ASTRA Agent - Portable Installer (pre-configured)
=================================================

Copy this whole folder to any Windows PC and run the installer as Administrator.
The PC enrolls into your ASTRA portal, sends telemetry, and gets the tray chat.
The enrollment token is already baked in - no need to paste anything.

INSTALL (run as Administrator)
  1. Right-click Start -> "Terminal (Admin)".
  2. cd into this folder.
  3. Run:
       powershell -ExecutionPolicy Bypass -File .\Install-AstraAgent.ps1

WHAT IT DOES
  - Installs the .NET 8 Desktop Runtime if missing (official Microsoft, signed).
  - Adds a hosts entry so the backend is reachable when corporate DNS can't resolve it.
  - Installs the ASTRA service (auto-start) + tray chat (auto-start at login) via the
    trusted dotnet host, so antivirus/ASR does not block them.

VERIFY
  - The device shows ONLINE in the portal within a minute.
  - An "ASTRA Assistant" tray icon appears (the chat).

Server:  @@SERVER_URL@@
Token expires:  @@EXPIRES@@

NOTE: this is a test/demo path. For a real fleet, code-sign the agent and have IT
allow the backend hostname (DNS + firewall) instead of the hosts-file entry.
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
        zf.writestr("README.txt", readme)
    return buffer.getvalue()
