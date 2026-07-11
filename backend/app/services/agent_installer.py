"""Generates a per-organization, pre-configured Windows agent installer.

The portal calls this after minting a one-time enrollment token. The returned
PowerShell script has the server URL and token baked in AND downloads the agent
binary from the backend itself (GET /api/v1/downloads/agent), so an admin only
needs to download this one small script and run it elevated — no separate build,
no .NET SDK, no dist folder.

Placeholders are substituted with str.replace (not str.format) so PowerShell's
own braces need no escaping.
"""

# @@SERVER_URL@@ and @@TOKEN@@ are replaced per request.
_INSTALL_TEMPLATE = r"""#Requires -RunAsAdministrator
<#
    ASTRA Windows Agent installer  —  pre-configured for your organization.

    HOW TO RUN:
      1. Right-click this file and choose "Run with PowerShell", OR
      2. In an elevated PowerShell:
             powershell -ExecutionPolicy Bypass -File .\Install-AstraAgent.ps1

    It downloads the agent from your ASTRA server, installs it as a Windows
    service, and enrolls this machine automatically. No other files are needed.
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

# 1. Remove any existing install so this is a clean, idempotent reinstall.
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping existing $ServiceName service..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# 2. Download the agent binary from the ASTRA server.
$zipPath     = Join-Path $env:TEMP "astra-agent.zip"
$downloadUrl = "$ServerUrl/api/v1/downloads/agent"
Write-Host "Downloading agent from $downloadUrl ..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing
} catch {
    throw "Could not download the agent from $downloadUrl. Check the server URL and that the ASTRA backend is reachable. $($_.Exception.Message)"
}

# 3. Extract into the install directory.
Write-Host "Installing to $InstallDir ..."
Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

$exePath = Join-Path $InstallDir $Exe
if (-not (Test-Path $exePath)) { throw "Expected $Exe in $InstallDir after extracting the agent." }

# 4. Write configuration (server URL + one-time enrollment token).
$config = @{
    Astra = @{
        ServerUrl                = $ServerUrl
        EnrollmentToken          = $EnrollmentToken
        HeartbeatIntervalSeconds = 60
    }
}
$config | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $InstallDir "appsettings.json") -Encoding UTF8

# 5. Register and start the Windows service.
Write-Host "Registering the $ServiceName service..."
sc.exe create $ServiceName binPath= "`"$exePath`"" start= auto | Out-Null
sc.exe description $ServiceName "ASTRA endpoint agent - telemetry and secure self-healing." | Out-Null
sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
Start-Service -Name $ServiceName

Write-Host "ASTRA agent installed and started. It will enroll and appear in your portal within a minute." -ForegroundColor Green
"""


def build_install_script(*, server_url: str, enrollment_token: str) -> str:
    return (
        _INSTALL_TEMPLATE
        .replace("@@SERVER_URL@@", server_url.rstrip("/"))
        .replace("@@TOKEN@@", enrollment_token)
    )
