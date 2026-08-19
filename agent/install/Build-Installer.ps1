#Requires -Version 5.1
<#
.SYNOPSIS
    Builds AstraAgent-Setup.exe — the single-file Windows installer.

.DESCRIPTION
    Stages the payload (see stage_installer_payload.py) and compiles
    AstraAgent.iss with Inno Setup, producing backend\downloads\AstraAgent-Setup.exe
    plus the sidecar manifest the backend reads before offering that download.

    The exe is compiled ONCE and served byte-identically to every organization —
    the enrollment key travels in the filename the backend serves it under. So this
    only needs re-running when the agent binaries or the install script change,
    not per customer.

.PARAMETER ServerUrl
    Backend the installer points at. Compiled in, so it must match the deployment's
    public_api_url; the backend refuses to serve an exe built for a different one.

.PARAMETER SignCommand
    Authenticode signing command, using Inno Setup's convention where $f stands in
    for the file being signed, e.g.
        'signtool.exe sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /f C:\cert.pfx /p pw $f'
    Defaults to $env:ASTRA_SIGNTOOL. When omitted the build is UNSIGNED, which is
    the state today: Windows will show SmartScreen's "Windows protected your PC" on
    first run, and Smart App Control may still block the agent DLLs. Supplying this
    is the whole of what changes when a certificate is finally obtained.

.EXAMPLE
    .\Build-Installer.ps1
#>
param(
    [string]$ServerUrl   = "https://api.astra.technomateai.com",
    [string]$OutputDir   = "",
    [string]$SignCommand = $env:ASTRA_SIGNTOOL
)

$ErrorActionPreference = "Stop"
$PRODUCTION_URL = "https://api.astra.technomateai.com"

$here    = $PSScriptRoot
$repo    = (Resolve-Path "$here\..\..").Path
$payload = Join-Path $here "payload"
# Default output is the committed location the backend serves from.
if (-not $OutputDir) { $OutputDir = Join-Path $repo "backend\downloads" }
$OutputDir = (New-Item -ItemType Directory -Force -Path $OutputDir).FullName
$outExe    = Join-Path $OutputDir "AstraAgent-Setup.exe"

# The backend URL is compiled in, and the default output path is a COMMITTED artefact.
# A throwaway build for localhost or staging left sitting there would ship an installer
# that enrols customers' machines into the wrong backend, so say so loudly.
$committedDir = (Join-Path $repo "backend\downloads")
if ($ServerUrl -ne $PRODUCTION_URL -and $OutputDir -eq $committedDir) {
    Write-Host ""
    Write-Host "  WARNING: building for $ServerUrl into the committed downloads folder." -ForegroundColor Red
    Write-Host "  Do NOT commit this exe. Rebuild without -ServerUrl before you do, or" -ForegroundColor Red
    Write-Host "  pass -OutputDir <somewhere else> for a throwaway build." -ForegroundColor Red
    Write-Host ""
}

function Find-Iscc {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        # winget installs Inno Setup per-user by default.
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Inno Setup 6 not found. Install it: winget install --id JRSoftware.InnoSetup"
}

# --- 1. Stage the payload -----------------------------------------------------
Write-Host "==== Staging payload ====" -ForegroundColor Cyan
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) { throw "Python not found; it stages the payload." }

$stageOut = & $python (Join-Path $here "stage_installer_payload.py") --server-url $ServerUrl 2>&1
$stageOut | ForEach-Object { Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) { throw "Staging failed." }

$version = ($stageOut | Select-String '^AGENT_VERSION=(.+)$').Matches.Groups[1].Value
if (-not $version) { throw "Staging did not report AGENT_VERSION." }

# --- 2. Sign the payload binaries ---------------------------------------------
# These have to be signed BEFORE compiling: Inno's own SignTool only signs the
# setup exe, and it is the DLLs inside that Smart App Control and Defender judge.
if ($SignCommand) {
    Write-Host "==== Signing payload binaries ====" -ForegroundColor Cyan
    foreach ($dll in @("dist-fd\AstraAgent.Service.dll", "dist-tray\AstraAgent.Tray.dll")) {
        $path = Join-Path $payload $dll
        $cmd  = $SignCommand.Replace('$f', '"' + $path + '"')
        Write-Host "  signing $dll"
        cmd.exe /c $cmd
        if ($LASTEXITCODE -ne 0) { throw "Signing failed for $dll (exit $LASTEXITCODE)." }
    }
} else {
    Write-Host "No signing command - building UNSIGNED." -ForegroundColor Yellow
    Write-Host "  SmartScreen will warn on first run and Smart App Control may still" -ForegroundColor Yellow
    Write-Host "  block the agent. Pass -SignCommand once a certificate exists." -ForegroundColor Yellow
}

# --- 3. Compile ---------------------------------------------------------------
Write-Host "==== Compiling installer ====" -ForegroundColor Cyan
$iscc = Find-Iscc
Write-Host "  ISCC: $iscc"

$isccArgs = @("/DAgentVersion=$version", "/O$OutputDir")
if ($SignCommand) {
    $isccArgs += "/DSIGN"
    $isccArgs += "/Sastra=$SignCommand"
}
$isccArgs += (Join-Path $here "AstraAgent.iss")

& $iscc @isccArgs
if ($LASTEXITCODE -ne 0) { throw "ISCC failed (exit $LASTEXITCODE)." }
if (-not (Test-Path $outExe)) { throw "ISCC reported success but $outExe is missing." }

# --- 4. Publish the sidecar the backend gates the download on -------------------
Copy-Item (Join-Path $here "payload-manifest.json") `
          (Join-Path $OutputDir "AstraAgent-Setup.json") -Force

$size = [math]::Round((Get-Item $outExe).Length / 1MB, 2)
$sig  = (Get-AuthenticodeSignature $outExe).Status

Write-Host ""
Write-Host "==== Done ====" -ForegroundColor Green
Write-Host "  $outExe"
Write-Host "  agent $version, $size MB, signature: $sig"
if ($sig -ne "Valid") {
    Write-Host "  UNSIGNED - expected until a code-signing certificate is in place." -ForegroundColor Yellow
}
