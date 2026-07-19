#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs the ASTRA agent (background Service + tray Chat) to run PERMANENTLY
    on this machine through the trusted `dotnet` host.

.DESCRIPTION
    On locked-down Windows (Defender ASR "block unsigned executables"), a
    standalone agent .exe is blocked. Running via dotnet.exe — which is
    Microsoft-signed and trusted — is allowed, with no code-signing certificate.

    Installs:
      - AstraAgent   : an auto-start Windows service (heartbeat + telemetry +
                       self-heal). Reuses the device credential already stored
                       via DPAPI (LocalMachine), so no re-enrollment is needed.
      - ASTRA Assistant : the tray chat, auto-starting at login (hidden console).

    Requires the .NET 8 runtime (the SDK includes it).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Install-Local-DotnetHost.ps1
#>
param(
    [string]$ServerUrl  = "https://api.astra.technomateai.com",
    [string]$ServiceSrc = "$PSScriptRoot\dist-fd",
    [string]$TraySrc    = "$PSScriptRoot\dist-tray"
)

$ErrorActionPreference = "Stop"

$dotnet = (Get-Command dotnet -ErrorAction SilentlyContinue).Source
if (-not $dotnet) { $dotnet = "$env:ProgramFiles\dotnet\dotnet.exe" }
if (-not (Test-Path $dotnet)) { throw "The .NET 8 runtime (dotnet.exe) was not found. Install it first." }

$ServerUrl = $ServerUrl.TrimEnd('/')
$svcName   = "AstraAgent"
$svcDir    = "$env:ProgramFiles\Astra\Agent"
$trayDir   = "$env:ProgramFiles\Astra\Tray"

Write-Host "== ASTRA agent (via dotnet host) -> $ServerUrl ==" -ForegroundColor Cyan

# ---------- Service: heartbeat + telemetry + self-heal ----------
if (Get-Service $svcName -ErrorAction SilentlyContinue) {
    Write-Host "Removing existing $svcName service..."
    Stop-Service $svcName -Force -ErrorAction SilentlyContinue
    sc.exe delete $svcName | Out-Null
    Start-Sleep -Seconds 2
}
New-Item -ItemType Directory -Force -Path $svcDir | Out-Null
Copy-Item "$ServiceSrc\*" $svcDir -Recurse -Force
if (-not (Test-Path "$svcDir\AstraAgent.Service.dll")) { throw "AstraAgent.Service.dll not found in $ServiceSrc — build dist-fd first." }

@{ Astra = @{ ServerUrl = $ServerUrl; HeartbeatIntervalSeconds = 60 } } |
    ConvertTo-Json -Depth 5 | Set-Content "$svcDir\appsettings.json" -Encoding UTF8

$svcBin = '"{0}" "{1}"' -f $dotnet, "$svcDir\AstraAgent.Service.dll"
New-Service -Name $svcName -BinaryPathName $svcBin -DisplayName "ASTRA Agent" `
    -Description "ASTRA endpoint agent - telemetry and secure self-healing." `
    -StartupType Automatic | Out-Null
# Auto-restart on crash.
sc.exe failure $svcName reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
Start-Service $svcName
Write-Host "Service '$svcName' installed and started." -ForegroundColor Green

# ---------- Tray: chat, per-user, auto-start at login (hidden) ----------
New-Item -ItemType Directory -Force -Path $trayDir | Out-Null
Copy-Item "$TraySrc\*" $trayDir -Recurse -Force
if (-not (Test-Path "$trayDir\AstraAgent.Tray.dll")) { throw "AstraAgent.Tray.dll not found in $TraySrc — build dist-tray first." }

@{ Astra = @{ ServerUrl = $ServerUrl } } |
    ConvertTo-Json -Depth 5 | Set-Content "$trayDir\appsettings.json" -Encoding UTF8

# A tiny VBScript launches dotnet hidden, so no black console window appears.
$vbs = "$trayDir\launch-tray.vbs"
@"
CreateObject("WScript.Shell").Run """$dotnet"" ""$trayDir\AstraAgent.Tray.dll""", 0, False
"@ | Set-Content $vbs -Encoding ASCII

# Auto-start at login for EVERY user on this machine (HKLM), so the tray appears
# after a restart without anyone running a command.
$runKey = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $runKey -Name "AstraAssistant" -Value ("wscript.exe `"$vbs`"")

# Launch it now too.
Start-Process wscript.exe -ArgumentList "`"$vbs`""
Write-Host "Tray 'ASTRA Assistant' installed, will auto-start at login, and launched now." -ForegroundColor Green

Start-Sleep -Seconds 3
Write-Host "== Status ==" -ForegroundColor Cyan
Get-Service $svcName | Select-Object Name, Status, StartType | Format-Table -AutoSize
Write-Host "Done. The service keeps your device online + sends telemetry; the tray icon is your chat." -ForegroundColor Green
Write-Host "Reboot to confirm both come back automatically." -ForegroundColor Yellow
