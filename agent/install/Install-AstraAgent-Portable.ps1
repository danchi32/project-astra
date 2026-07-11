#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Portable ASTRA agent installer — copy this whole folder to any Windows PC and run.

.DESCRIPTION
    Installs the ASTRA agent (background Service + tray Chat) so the device enrolls
    and appears in your portal. Handles the three things that block locked-down
    corporate machines:

      1. Unsigned-exe ASR block  -> runs everything via the trusted `dotnet` host.
      2. .NET 8 runtime missing   -> installs the official (signed) runtime if needed.
      3. Corporate DNS can't see the backend -> adds a hosts entry to the backend IP.

    One enrollment token works for every machine (reusable until it expires).

.PARAMETER EnrollmentToken
    A token from the portal (Devices -> Install agent -> Generate). Required.

.PARAMETER ServerUrl
    Backend URL. Defaults to your Railway backend.

.PARAMETER BackendIp
    IP to pin the backend hostname to in the hosts file (for networks whose DNS
    can't resolve it). Pass "" to skip if the machine's DNS already works.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Install-AstraAgent-Portable.ps1 -EnrollmentToken abc123
#>
param(
    [Parameter(Mandatory = $true)][string]$EnrollmentToken,
    [string]$ServerUrl = "https://astra-backend-production-9ee2.up.railway.app",
    [string]$BackendIp = "69.46.46.120",
    [string]$ServiceSrc = "$PSScriptRoot\dist-fd",
    [string]$TraySrc    = "$PSScriptRoot\dist-tray"
)

$ErrorActionPreference = "Stop"
$ServerUrl = $ServerUrl.TrimEnd('/')
$fqdn = ([Uri]$ServerUrl).Host
$svcName = "AstraAgent"
$svcDir  = "$env:ProgramFiles\Astra\Agent"
$trayDir = "$env:ProgramFiles\Astra\Tray"

Write-Host "==== ASTRA agent portable installer ====" -ForegroundColor Cyan
Write-Host "Backend: $ServerUrl" -ForegroundColor Cyan

# ---------- 1. Ensure the .NET 8 Desktop runtime (needed by the tray + agent) ----------
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
    Write-Host "Installing the .NET 8 Desktop Runtime (Microsoft, signed)..." -ForegroundColor Yellow
    $rt = "$env:TEMP\windowsdesktop-runtime-8-win-x64.exe"
    try {
        Invoke-WebRequest -Uri "https://aka.ms/dotnet/8.0/windowsdesktop-runtime-win-x64.exe" -OutFile $rt -UseBasicParsing
        Start-Process -FilePath $rt -ArgumentList "/quiet","/norestart" -Wait
    } catch {
        throw "Could not download/install the .NET 8 Desktop Runtime. Install it manually from https://dotnet.microsoft.com/download/dotnet/8.0 then re-run. $($_.Exception.Message)"
    }
    $dotnet = Get-DotnetHost
    if (-not (Test-Path $dotnet)) { throw ".NET runtime install did not complete." }
}
Write-Host "dotnet host: $dotnet" -ForegroundColor Green

# ---------- 2. Make the backend reachable (corporate DNS often can't resolve it) ----------
if ($BackendIp) {
    $resolves = $false
    try { $resolves = [bool](Resolve-DnsName $fqdn -ErrorAction Stop) } catch { $resolves = $false }
    if (-not $resolves) {
        Write-Host "System DNS can't resolve $fqdn — adding hosts entry -> $BackendIp" -ForegroundColor Yellow
        $hostsFile = "$env:windir\System32\drivers\etc\hosts"
        (Get-Content $hostsFile) -notmatch ([regex]::Escape($fqdn)) | Set-Content $hostsFile
        Add-Content $hostsFile "$BackendIp $fqdn"
        ipconfig /flushdns | Out-Null
    }
    if (-not (Test-NetConnection $fqdn -Port 443 -InformationLevel Quiet)) {
        Write-Host "WARNING: still can't reach $fqdn on 443. The firewall may be blocking it." -ForegroundColor Red
    }
}

# ---------- 3. Install the Service (heartbeat + telemetry + self-heal) ----------
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

# ---------- 4. Install the Tray chat (auto-start at login, hidden) ----------
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
Write-Host "==== Status ====" -ForegroundColor Cyan
Get-Service $svcName | Select-Object Name, Status, StartType | Format-Table -AutoSize
Write-Host "Done. This device should appear ONLINE in your ASTRA portal within a minute." -ForegroundColor Green
