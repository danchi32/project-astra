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
    Backend URL. Defaults to the ASTRA production API on its custom domain.

.PARAMETER BackendIp
    Optional IP to pin $ServerUrl's hostname to in the hosts file, for networks
    whose DNS cannot resolve it. EMPTY BY DEFAULT and it should stay that way:
    a hosts pin overrides DNS, so a stale one blackholes the agent permanently
    once the backend IP changes. Use only as a temporary workaround.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Install-AstraAgent-Portable.ps1 -EnrollmentToken abc123
#>
param(
    [Parameter(Mandatory = $true)][string]$EnrollmentToken,
    [string]$ServerUrl = "https://api.astra.technomateai.com",
    [string]$BackendIp = "",
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

# ---------- 2. Confirm the backend is reachable ----------
# Only touch the hosts file if it genuinely is not. A hosts pin OVERRIDES working
# DNS, so writing one we do not need is harmful: when the backend IP later changes,
# the stale pin blackholes this agent and outlives the cause.
function Test-BackendReachable {
    try {
        Invoke-WebRequest -Uri "$ServerUrl/health" -UseBasicParsing -TimeoutSec 10 | Out-Null
        return $true
    } catch {
        # Any HTTP response (401/404/500) still proves the host was reached.
        return [bool]$_.Exception.Response
    }
}

if (Test-BackendReachable) {
    Write-Host "Backend is reachable - no hosts change needed." -ForegroundColor Green
} elseif ($BackendIp) {
    Write-Host "Backend not reachable via DNS - pinning $fqdn -> $BackendIp" -ForegroundColor Yellow
    $hostsFile = "$env:windir\System32\drivers\etc\hosts"
    $written = $false
    foreach ($attempt in 1..3) {
        try {
            # One atomic write. Writing twice (Set-Content then Add-Content) races
            # its own file handle against Defender's on-close scan of hosts.
            $lines = @(Get-Content -LiteralPath $hostsFile -ErrorAction Stop)
            $kept  = @($lines | Where-Object { $_ -notmatch [regex]::Escape($fqdn) })
            $kept += "$BackendIp $fqdn"
            Set-Content -LiteralPath $hostsFile -Value $kept -Encoding ASCII -Force -ErrorAction Stop
            $written = $true
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if ($written) {
        ipconfig /flushdns | Out-Null
        Write-Host "Hosts entry added." -ForegroundColor Green
    } else {
        # An optimization, never a requirement - do NOT fail the install over it.
        Write-Host "WARNING: could not write the hosts file (locked - usually antivirus)." -ForegroundColor Yellow
        Write-Host "         Continuing. Ask IT to allow $fqdn through DNS + firewall." -ForegroundColor Yellow
    }
} else {
    Write-Host "WARNING: $ServerUrl is not reachable from this PC. Installing anyway;" -ForegroundColor Yellow
    Write-Host "         the agent retries until it becomes reachable. Ask IT to allow" -ForegroundColor Yellow
    Write-Host "         $fqdn through DNS and the firewall (443)." -ForegroundColor Yellow
}

# ---------- 3. Install the Service (heartbeat + telemetry + self-heal) ----------
# Tear the old install down properly. `sc delete` unregisters the service but does
# NOT kill its process — and this service is hosted by dotnet.exe, which keeps
# AstraAgent.Service.dll locked. Without waiting for the process to actually die,
# the Copy-Item below fails with "being used by another process".
if (Get-Service $svcName -ErrorAction SilentlyContinue) {
    Write-Host "Removing the existing $svcName service..."
    Stop-Service $svcName -Force -ErrorAction SilentlyContinue

    $deadline = 20
    while ($deadline-- -gt 0) {
        $s = Get-Service $svcName -ErrorAction SilentlyContinue
        if (-not $s -or $s.Status -eq 'Stopped') { break }
        Start-Sleep -Seconds 1
    }
    $old = Get-CimInstance Win32_Service -Filter "Name='$svcName'" -ErrorAction SilentlyContinue
    if ($old -and $old.ProcessId -and $old.ProcessId -ne 0) {
        Stop-Process -Id $old.ProcessId -Force -ErrorAction SilentlyContinue
    }

    sc.exe delete $svcName | Out-Null
    $deadline = 15
    while ($deadline-- -gt 0) {
        if (-not (Get-Service $svcName -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Seconds 1
    }
    if (Get-Service $svcName -ErrorAction SilentlyContinue) {
        throw "The $svcName service is still registered (marked for deletion). Close services.msc and Task Manager, then re-run. A reboot always clears it."
    }
}

# Kill any orphaned host still holding the agent/tray DLLs.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'AstraAgent\.(Service|Tray)|launch-tray\.vbs' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

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
Set-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "AstraAssistant" -Value ("wscript.exe `"$vbs`"")
Start-Process wscript.exe -ArgumentList "`"$vbs`""
Write-Host "Tray chat installed and launched." -ForegroundColor Green

Start-Sleep -Seconds 4
Write-Host "==== Status ====" -ForegroundColor Cyan
Get-Service $svcName | Select-Object Name, Status, StartType | Format-Table -AutoSize
Write-Host "Done. This device should appear ONLINE in your ASTRA portal within a minute." -ForegroundColor Green
