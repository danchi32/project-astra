#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Stops and removes the ASTRA Windows agent from this machine.
.DESCRIPTION
    Deletes the AstraAgent service and its install directory. The device credential
    under C:\ProgramData\Astra is removed too unless -KeepCredential is given, so a
    later reinstall re-enrolls cleanly.
#>
param(
    [string]$InstallDir = "$env:ProgramFiles\Astra\Agent",
    [switch]$KeepCredential
)

$ErrorActionPreference = "Stop"
$ServiceName = "AstraAgent"

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping and removing $ServiceName service..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
} else {
    Write-Host "$ServiceName service not found."
}

if (Test-Path $InstallDir) { Remove-Item -Path $InstallDir -Recurse -Force }

if (-not $KeepCredential) {
    $cred = "$env:ProgramData\Astra"
    if (Test-Path $cred) { Remove-Item -Path $cred -Recurse -Force }
}

Write-Host "ASTRA agent uninstalled." -ForegroundColor Green
