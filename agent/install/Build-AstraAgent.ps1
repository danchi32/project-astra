<#
.SYNOPSIS
    Publishes a self-contained ASTRA agent build you can distribute to endpoints.

.DESCRIPTION
    Produces a single-file, self-contained win-x64 build (no .NET runtime required
    on the target) in the output folder. Ship that folder (or a zip of it) alongside
    Install-AstraAgent.ps1 and install with:  Install-AstraAgent.ps1 -Source <folder>

.EXAMPLE
    .\Build-AstraAgent.ps1                 # -> agent\install\dist
    .\Build-AstraAgent.ps1 -Output C:\out  # custom location
#>
param(
    [string]$Output = "$PSScriptRoot\dist",
    [switch]$Zip
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { throw "The .NET 8 SDK is required." }

$repo = Split-Path -Parent $PSScriptRoot   # agent\
$proj = Join-Path $repo "src\AstraAgent.Service"

Write-Host "Publishing self-contained agent -> $Output" -ForegroundColor Cyan
dotnet publish $proj -c Release -r win-x64 --self-contained true `
    -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o $Output

if ($Zip) {
    $zipPath = "$Output.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path (Join-Path $Output "*") -DestinationPath $zipPath
    Write-Host "Zipped -> $zipPath" -ForegroundColor Green
}

Write-Host "Done. Distribute the build with Install-AstraAgent.ps1 -Source `"$Output`"" -ForegroundColor Green
