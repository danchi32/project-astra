#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs the ASTRA Windows agent as a service on this machine.

.DESCRIPTION
    Registers AstraAgent.Service.exe as an auto-start Windows service, writes its
    configuration (server URL + one-time enrollment token) and starts it. On first
    run the agent enrolls itself and appears in the ASTRA portal.

    Get the binaries one of three ways:
      -Source <folder|zip>   install a published build (see Build-AstraAgent.ps1)
      -BuildFromSource       publish from a repo checkout (needs the .NET 8 SDK)
      (default)              use a "dist" folder next to this script, if present

    The ASTRA portal (Devices -> Install agent) can generate a copy of this script
    with -ServerUrl and -EnrollmentToken already filled in.

.EXAMPLE
    .\Install-AstraAgent.ps1 -ServerUrl https://astra.example.com -EnrollmentToken abc123 -Source .\dist

.EXAMPLE
    .\Install-AstraAgent.ps1 -ServerUrl http://localhost:8000 -EnrollmentToken abc123 -BuildFromSource
#>
param(
    [Parameter(Mandatory = $true)][string]$ServerUrl,
    [Parameter(Mandatory = $true)][string]$EnrollmentToken,
    [string]$InstallDir = "$env:ProgramFiles\Astra\Agent",
    [string]$Source = "",
    [switch]$BuildFromSource
)

$ErrorActionPreference = "Stop"
$ServiceName = "AstraAgent"
$Exe = "AstraAgent.Service.exe"

Write-Host "ASTRA agent -> $ServerUrl" -ForegroundColor Cyan

# 1. Clean, idempotent reinstall.
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping existing $ServiceName service..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# 2. Obtain the agent binaries.
function Copy-Published($from) {
    if ($from.ToLower().EndsWith(".zip")) {
        Expand-Archive -Path $from -DestinationPath $InstallDir -Force
    } else {
        Copy-Item -Path (Join-Path $from "*") -Destination $InstallDir -Recurse -Force
    }
}

if ($Source) {
    Write-Host "Installing from $Source"
    Copy-Published $Source
} elseif ($BuildFromSource) {
    if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { throw "The .NET 8 SDK is required for -BuildFromSource." }
    $repo = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
    $proj = Join-Path $repo "src\AstraAgent.Service"
    Write-Host "Publishing self-contained build from $proj ..."
    dotnet publish $proj -c Release -r win-x64 --self-contained true `
        -p:PublishSingleFile=true -o $InstallDir
} else {
    $localDist = Join-Path (Split-Path -Parent $PSCommandPath) "dist"
    if (Test-Path (Join-Path $localDist $Exe)) {
        Copy-Published $localDist
    } else {
        throw "No agent binaries found. Pass -Source <published build> or -BuildFromSource. See README.md."
    }
}

$exePath = Join-Path $InstallDir $Exe
if (-not (Test-Path $exePath)) { throw "Expected $Exe in $InstallDir after install." }

# 3. Write configuration.
$config = @{
    Astra = @{
        ServerUrl                = $ServerUrl
        EnrollmentToken          = $EnrollmentToken
        HeartbeatIntervalSeconds = 60
    }
}
$config | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $InstallDir "appsettings.json") -Encoding UTF8

# 4. Register and start the service.
Write-Host "Registering the $ServiceName service..."
sc.exe create $ServiceName binPath= "`"$exePath`"" start= auto | Out-Null
sc.exe description $ServiceName "ASTRA endpoint agent - telemetry and secure self-healing." | Out-Null
sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
Start-Service -Name $ServiceName

Write-Host "ASTRA agent installed and started. It will enroll and appear in your portal shortly." -ForegroundColor Green
