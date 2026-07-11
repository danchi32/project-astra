"""Generates per-organization, pre-configured Windows agent installers.

Two shapes, both minting a reusable enrollment token (one token can enroll any
number of machines — enroll() keys devices by machine id and never consumes the
token, so it works for mass deployment):

- Online installer  (build_install_script): a small .ps1 that downloads the agent
  from the backend at install time. Good for one or a few machines.
- Offline bundle     (build_offline_bundle_zip): a single .zip containing the agent
  binary + Install.bat + an install script that installs from the bundled binary,
  with server URL and token baked in. Copy to any number of PCs and run once each.

Placeholders are substituted with str.replace (not str.format) so PowerShell's
own braces need no escaping.
"""
import io
import zipfile
from pathlib import Path

# agent_installer.py lives at <app_root>/app/services/; the baked binary sits at
# <app_root>/downloads/agent.zip. Resolve relative to this file so it works
# regardless of the container's working directory.
AGENT_ZIP = Path(__file__).resolve().parents[2] / "downloads" / "agent.zip"


# ── Online installer: downloads the agent from the backend at install time ──────
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

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping existing $ServiceName service..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$zipPath     = Join-Path $env:TEMP "astra-agent.zip"
$downloadUrl = "$ServerUrl/api/v1/downloads/agent"
Write-Host "Downloading agent from $downloadUrl ..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing
} catch {
    throw "Could not download the agent from $downloadUrl. Check the server URL and that the ASTRA backend is reachable. $($_.Exception.Message)"
}

Write-Host "Installing to $InstallDir ..."
Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

$exePath = Join-Path $InstallDir $Exe
if (-not (Test-Path $exePath)) { throw "Expected $Exe in $InstallDir after extracting the agent." }

$config = @{
    Astra = @{
        ServerUrl                = $ServerUrl
        EnrollmentToken          = $EnrollmentToken
        HeartbeatIntervalSeconds = 60
    }
}
$config | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $InstallDir "appsettings.json") -Encoding UTF8

Write-Host "Registering the $ServiceName service..."
sc.exe create $ServiceName binPath= "`"$exePath`"" start= auto | Out-Null
sc.exe description $ServiceName "ASTRA endpoint agent - telemetry and secure self-healing." | Out-Null
sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
Start-Service -Name $ServiceName

Write-Host "ASTRA agent installed and started. It will enroll and appear in your portal within a minute." -ForegroundColor Green
"""


# ── Offline installer: installs from the agent.zip bundled alongside it ─────────
_OFFLINE_INSTALL_TEMPLATE = r"""#Requires -RunAsAdministrator
<#
    ASTRA Windows Agent — OFFLINE installer (pre-configured for your organization).

    Installs the agent from the agent.zip bundled in this same folder — no
    download needed at install time. The machine still reports to your ASTRA
    server once installed. The enrollment token is reusable across every PC.

    HOW TO RUN: right-click Install.bat -> Run as administrator.
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

Write-Host "ASTRA agent (offline) -> $ServerUrl" -ForegroundColor Cyan

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping existing $ServiceName service..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$bundle = Join-Path $PSScriptRoot "agent.zip"
if (-not (Test-Path $bundle)) { throw "agent.zip was not found next to this script. Keep the whole folder together." }
Write-Host "Installing to $InstallDir ..."
Expand-Archive -Path $bundle -DestinationPath $InstallDir -Force

$exePath = Join-Path $InstallDir $Exe
if (-not (Test-Path $exePath)) { throw "Expected $Exe in $InstallDir after extracting the agent." }

$config = @{
    Astra = @{
        ServerUrl                = $ServerUrl
        EnrollmentToken          = $EnrollmentToken
        HeartbeatIntervalSeconds = 60
    }
}
$config | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $InstallDir "appsettings.json") -Encoding UTF8

Write-Host "Registering the $ServiceName service..."
sc.exe create $ServiceName binPath= "`"$exePath`"" start= auto | Out-Null
sc.exe description $ServiceName "ASTRA endpoint agent - telemetry and secure self-healing." | Out-Null
sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
Start-Service -Name $ServiceName

Write-Host "ASTRA agent installed and started. It will enroll and appear in your portal within a minute." -ForegroundColor Green
"""


# Double-clickable wrapper. Right-click -> Run as administrator (or elevate here).
_INSTALL_BAT = """@echo off
REM ASTRA agent offline installer. Right-click this file -> "Run as administrator".
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-AstraAgent.ps1"
if %errorlevel% neq 0 (
  echo.
  echo Installation failed. Make sure you ran this as Administrator.
  pause
)
"""

_README = """ASTRA Agent - Offline Installer
================================

Deploy this agent to any number of Windows PCs. Each PC appears in your ASTRA
portal automatically, under Devices.

CONTENTS
  Install.bat              <- run this
  Install-AstraAgent.ps1   the installer (server URL + enrollment token baked in)
  agent.zip                the agent binaries

INSTALL ON ONE PC
  1. Copy this whole folder to the PC (USB, network share, etc.).
  2. Right-click Install.bat  ->  Run as administrator.
  3. The PC enrolls and shows up under Devices within a minute.

MASS DEPLOYMENT (many PCs)
  Deploy via Group Policy / Intune / SCCM by running this as SYSTEM or admin:
     powershell -ExecutionPolicy Bypass -File Install-AstraAgent.ps1
  The enrollment token is reusable for every PC until it expires.

Server:  @@SERVER_URL@@
Token expires:  @@EXPIRES@@
"""


def build_install_script(*, server_url: str, enrollment_token: str) -> str:
    return (
        _INSTALL_TEMPLATE
        .replace("@@SERVER_URL@@", server_url.rstrip("/"))
        .replace("@@TOKEN@@", enrollment_token)
    )


def build_offline_bundle_zip(
    *, server_url: str, enrollment_token: str, expires_label: str
) -> bytes:
    """Assemble the single-file offline installer: agent binary + a pre-keyed
    install script + a double-clickable Install.bat + a README, as one .zip."""
    if not AGENT_ZIP.is_file():
        raise FileNotFoundError(
            "Agent binary is not bundled with this deployment "
            "(backend/downloads/agent.zip). Commit it and redeploy."
        )

    url = server_url.rstrip("/")
    script = (
        _OFFLINE_INSTALL_TEMPLATE
        .replace("@@SERVER_URL@@", url)
        .replace("@@TOKEN@@", enrollment_token)
    )
    readme = _README.replace("@@SERVER_URL@@", url).replace("@@EXPIRES@@", expires_label)

    agent_bytes = AGENT_ZIP.read_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # agent.zip is already compressed — store it as-is to avoid re-deflating.
        zf.writestr("agent.zip", agent_bytes, compress_type=zipfile.ZIP_STORED)
        zf.writestr("Install-AstraAgent.ps1", script)
        zf.writestr("Install.bat", _INSTALL_BAT)
        zf.writestr("README.txt", readme)
    return buffer.getvalue()
