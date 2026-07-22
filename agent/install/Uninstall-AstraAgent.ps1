#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Completely removes the ASTRA Windows agent (Service + Tray) from this machine.

.DESCRIPTION
    Reverses everything either installer creates, and - unlike a naive
    "Stop-Service + sc delete" - guarantees the service process is really dead
    before deleting files. That matters because the portable install hosts the
    service as `dotnet.exe AstraAgent.Service.dll`: `sc delete` unregisters the
    service but never kills the process, so the DLL stays locked and the next
    install fails with "already in use" / "service already exists".

    Steps:
      1. Stop the service, wait for it to really stop, force-kill the PID if not
      2. Delete the service, verify it is gone (detects "marked for deletion")
      3. Kill any lingering dotnet/wscript host holding the agent or tray DLLs
      4. Remove the tray auto-start (Run\AstraAssistant)
      5. Delete install dirs, retrying once locks are released
      6. Remove device credential + per-user data + hosts pin

.PARAMETER KeepCredential
    Leave the device credential under ProgramData\Astra in place.

.PARAMETER BackendHosts
    Hostnames to strip from the hosts file. Defaults to every backend ASTRA has
    shipped, because a machine in the field may carry a pin from any past
    installer - leaving a stale pin behind would blackhole a future reinstall.
    Pass @() to leave the hosts file alone.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Uninstall-AstraAgent.ps1
#>
param(
    [string]$InstallDir = "$env:ProgramFiles\Astra\Agent",
    [string]$TrayDir    = "$env:ProgramFiles\Astra\Tray",
    [string[]]$BackendHosts = @(
        "api.astra.technomateai.com",
        "astra-backend-production-9ee2.up.railway.app"
    ),
    [switch]$KeepCredential
)

$ErrorActionPreference = "Continue"   # best-effort: never abort the cleanup half-done
$ServiceName = "AstraAgent"
$script:Problems = @()

Write-Host "==== Uninstalling ASTRA agent ====" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Stop the service for real (not just "ask nicely and hope").
# ---------------------------------------------------------------------------
$svc = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host "Stopping the $ServiceName service..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue

    # Wait up to 20s for a genuine Stopped state (Stop-Service can return while
    # the service sits in STOP_PENDING).
    $deadline = 20
    while ($deadline-- -gt 0) {
        $s = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if (-not $s -or $s.Status -eq 'Stopped') { break }
        Start-Sleep -Seconds 1
    }

    # Still alive? Kill the hosting process by PID. This is the step the old
    # script was missing, and the reason files stayed locked.
    $svc = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
    if ($svc -and $svc.ProcessId -and $svc.ProcessId -ne 0) {
        Write-Host "Service did not stop cleanly - force-killing PID $($svc.ProcessId)." -ForegroundColor Yellow
        Stop-Process -Id $svc.ProcessId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
} else {
    Write-Host "$ServiceName service not found (already removed)."
}

# ---------------------------------------------------------------------------
# 2. Delete the service and verify. Report "marked for deletion" honestly.
# ---------------------------------------------------------------------------
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Removing the $ServiceName service registration..."
    sc.exe delete $ServiceName | Out-Null

    $deadline = 10
    while ($deadline-- -gt 0) {
        if (-not (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Seconds 1
    }

    if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
        # A handle is still open (usually services.msc or Task Manager's
        # Services tab). Drop the registry key so a reinstall can recreate it.
        $key = "HKLM:\SYSTEM\CurrentControlSet\Services\$ServiceName"
        if (Test-Path $key) { Remove-Item $key -Recurse -Force -ErrorAction SilentlyContinue }
        if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
            $script:Problems += "The $ServiceName service is 'marked for deletion' - something still holds a handle to it. CLOSE services.msc and Task Manager, then re-run this uninstaller. If it persists, reboot; it will be gone on restart."
        }
    }
}

# ---------------------------------------------------------------------------
# 3. Kill lingering hosts that keep the agent/tray DLLs locked.
#    (dotnet.exe hosting the DLLs, wscript.exe running launch-tray.vbs.)
# ---------------------------------------------------------------------------
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'AstraAgent\.(Service|Tray)|launch-tray\.vbs|Astra\\(Agent|Tray)' } |
    ForEach-Object {
        Write-Host "Stopping leftover process $($_.Name) (PID $($_.ProcessId))..."
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Get-Process -Name "AstraAgent.Service","AstraAgent.Tray" -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# ---------------------------------------------------------------------------
# 4. Tray auto-start.
# ---------------------------------------------------------------------------
$runKey = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
if (Get-ItemProperty -Path $runKey -Name "AstraAssistant" -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $runKey -Name "AstraAssistant" -ErrorAction SilentlyContinue
    Write-Host "Removed tray auto-start (Run\AstraAssistant)."
}

# ---------------------------------------------------------------------------
# 5. Install directories - retry, since a lock may take a moment to release.
# ---------------------------------------------------------------------------
function Remove-Tree($path) {
    if (-not (Test-Path $path)) { return $true }
    foreach ($attempt in 1..3) {
        Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
        if (-not (Test-Path $path)) { return $true }
        Start-Sleep -Seconds 2
    }
    return -not (Test-Path $path)
}

foreach ($dir in @($InstallDir, $TrayDir)) {
    if (Test-Path $dir) {
        if (Remove-Tree $dir) {
            Write-Host "Removed $dir"
        } else {
            $script:Problems += "Could not delete $dir - a file there is still locked. Reboot and re-run this uninstaller."
        }
    }
}
$parent = Split-Path $InstallDir -Parent
if ((Test-Path $parent) -and -not (Get-ChildItem $parent -Force -ErrorAction SilentlyContinue)) {
    Remove-Item $parent -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# 6. Credential, per-user data, hosts pin.
# ---------------------------------------------------------------------------
if (-not $KeepCredential) {
    $cred = "$env:ProgramData\Astra"
    if (Test-Path $cred) {
        if (Remove-Tree $cred) { Write-Host "Removed device credential ($cred)." }
    }
}

$usersRoot = Split-Path $env:USERPROFILE -Parent
Get-ChildItem $usersRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $p = Join-Path $_.FullName "AppData\Local\Astra"
    if (Test-Path $p) {
        if (Remove-Tree $p) { Write-Host "Removed per-user data ($p)." }
    }
}

if ($BackendHosts -and $BackendHosts.Count -gt 0) {
    $hostsFile = "$env:windir\System32\drivers\etc\hosts"
    if (Test-Path $hostsFile) {
        # One read, one filtered write - retried, because Defender scans the hosts
        # file on close and briefly locks it (writing it twice in a row fails).
        foreach ($attempt in 1..3) {
            try {
                $lines = @(Get-Content -LiteralPath $hostsFile -ErrorAction Stop)
                $kept  = @($lines | Where-Object {
                    $line = $_
                    -not ($BackendHosts | Where-Object { $line -match [regex]::Escape($_) })
                })
                if ($kept.Count -eq $lines.Count) { break }   # nothing of ours in there
                Set-Content -LiteralPath $hostsFile -Value $kept -Encoding ASCII -Force -ErrorAction Stop
                ipconfig /flushdns | Out-Null
                Write-Host "Removed ASTRA hosts entries."
                break
            } catch {
                if ($attempt -eq 3) {
                    $script:Problems += "Could not clean the hosts file - it is locked (usually antivirus). Remove any ASTRA line from $hostsFile by hand, or a stale pin may blackhole a reinstall."
                }
                Start-Sleep -Seconds 2
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Verdict - tell the truth about whether a reinstall will succeed.
# ---------------------------------------------------------------------------
Write-Host ""
if ($script:Problems.Count -eq 0) {
    Write-Host "ASTRA agent fully uninstalled. This machine is clean for a reinstall." -ForegroundColor Green
    Write-Host "The device will show OFFLINE in the portal; remove it there to delete its record." -ForegroundColor DarkGray
} else {
    Write-Host "Uninstall finished WITH PROBLEMS - a reinstall may fail:" -ForegroundColor Red
    $script:Problems | ForEach-Object { Write-Host "  * $_" -ForegroundColor Yellow }
    exit 1
}
