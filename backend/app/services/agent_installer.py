"""Generates a per-organization, pre-configured Windows agent installer.

The portal calls this after minting a one-time enrollment token; the returned
PowerShell script has the server URL and token baked in so an admin can run it
on a target machine with no further configuration. It mirrors the committed
reference installer at agent/install/Install-AstraAgent.ps1.
"""

# {server_url} and {token} are filled per request. Doubled braces are literal PowerShell.
_INSTALL_TEMPLATE = r"""#Requires -RunAsAdministrator
<#
    ASTRA Windows Agent installer  —  pre-configured for your organization.

    Run on the target machine in an elevated PowerShell:
        powershell -ExecutionPolicy Bypass -File .\Install-AstraAgent.ps1

    Pair this script with a published agent build (see agent/install/README.md):
      - pass -Source <folder|zip> pointing at the published binaries, or
      - run with -BuildFromSource from a repo checkout that has the .NET 8 SDK.
#>
param(
    [string]$ServerUrl        = "{server_url}",
    [string]$EnrollmentToken  = "{token}",
    [string]$InstallDir       = "$env:ProgramFiles\Astra\Agent",
    [string]$Source           = "",
    [switch]$BuildFromSource
)

$ErrorActionPreference = "Stop"
$ServiceName = "AstraAgent"
$Exe         = "AstraAgent.Service.exe"

if ([string]::IsNullOrWhiteSpace($ServerUrl))       {{ throw "ServerUrl is required." }}
if ([string]::IsNullOrWhiteSpace($EnrollmentToken)) {{ throw "EnrollmentToken is required." }}

Write-Host "ASTRA agent -> $ServerUrl" -ForegroundColor Cyan

# 1. Remove any existing install so this is a clean, idempotent reinstall.
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {{
    Write-Host "Stopping existing $ServiceName service..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# 2. Obtain the agent binaries.
function Copy-Published($from) {{
    if ($from.ToLower().EndsWith(".zip")) {{
        Expand-Archive -Path $from -DestinationPath $InstallDir -Force
    }} else {{
        Copy-Item -Path (Join-Path $from "*") -Destination $InstallDir -Recurse -Force
    }}
}}

if ($Source) {{
    Write-Host "Installing from $Source"
    Copy-Published $Source
}} elseif ($BuildFromSource) {{
    if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {{ throw "The .NET 8 SDK is required for -BuildFromSource." }}
    $repo = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
    $proj = Join-Path $repo "src\AstraAgent.Service"
    Write-Host "Publishing self-contained build from $proj ..."
    dotnet publish $proj -c Release -r win-x64 --self-contained true `
        -p:PublishSingleFile=true -o $InstallDir
}} else {{
    $localDist = Join-Path (Split-Path -Parent $PSCommandPath) "dist"
    if (Test-Path (Join-Path $localDist $Exe)) {{
        Copy-Published $localDist
    }} else {{
        throw "No agent binaries found. Pass -Source <published build> or -BuildFromSource. See agent/install/README.md."
    }}
}}

$exePath = Join-Path $InstallDir $Exe
if (-not (Test-Path $exePath)) {{ throw "Expected $Exe in $InstallDir after install." }}

# 3. Write configuration (server URL + one-time enrollment token).
$config = @{{
    Astra = @{{
        ServerUrl                = $ServerUrl
        EnrollmentToken          = $EnrollmentToken
        HeartbeatIntervalSeconds = 60
    }}
}}
$config | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $InstallDir "appsettings.json") -Encoding UTF8

# 4. Register and start the Windows service.
Write-Host "Registering the $ServiceName service..."
sc.exe create $ServiceName binPath= "`"$exePath`"" start= auto | Out-Null
sc.exe description $ServiceName "ASTRA endpoint agent — telemetry and secure self-healing." | Out-Null
sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
Start-Service -Name $ServiceName

Write-Host "ASTRA agent installed and started. It will enroll and appear in your portal shortly." -ForegroundColor Green
"""


def build_install_script(*, server_url: str, enrollment_token: str) -> str:
    return _INSTALL_TEMPLATE.format(
        server_url=server_url.rstrip("/"),
        token=enrollment_token,
    )
