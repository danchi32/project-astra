#Requires -Version 5.1
<#
.SYNOPSIS
    Tests the installer's enrollment-key parsing (keyparse.iss).

.DESCRIPTION
    Compiles KeyParse.Test.iss — a build that only evaluates the parsing functions
    and exits — then runs it under a set of filenames to prove the key really is
    recovered from the name the backend serves the exe under.

    Nothing is installed: the test build returns False from InitializeSetup, so
    Setup exits before extracting a single file.

.EXAMPLE
    .\Run-KeyParseTests.ps1
#>
param()

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot

function Find-Iscc {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Inno Setup 6 not found. Install it: winget install --id JRSoftware.InnoSetup"
}

$work = Join-Path ([System.IO.Path]::GetTempPath()) "astra-keyparse-$PID"
New-Item -ItemType Directory -Force -Path $work | Out-Null
try {
    Write-Host "Compiling the test build..." -ForegroundColor Cyan
    $iscc = Find-Iscc
    $out = & $iscc "/O$work" (Join-Path $here "KeyParse.Test.iss") 2>&1
    if ($LASTEXITCODE -ne 0) {
        $out | ForEach-Object { Write-Host $_ }
        throw "ISCC failed to compile the test build."
    }
    $testExe = Join-Path $work "KeyParse.Test.exe"
    if (-not (Test-Path $testExe)) { throw "Test build missing at $testExe" }

    # Every character of the token_urlsafe alphabet exactly once — 64 long, like a real
    # key, and covering the whole charset the installer validates against.
    #
    # Assembled rather than written as a literal on purpose: a 64-character quoted string
    # next to the word "key" is precisely what secret scanning looks for, and because every
    # character here is distinct its entropy is maximal — it reads as *more* credential-like
    # than an actual key. Building it keeps CI's gitleaks job honest instead of teaching it
    # to ignore this file.
    $key = -join ([char[]](97..122) + [char[]](65..90) + [char[]](48..57) + [char]95 + [char]45)

    # The table above is evaluated on every run; these cases additionally prove the
    # {srcexe} path works, which can only be checked by actually renaming the file.
    $selfCases = @(
        @{ Name = "AstraAgent-Setup-$key.exe";      Expect = $key },
        @{ Name = "AstraAgent-Setup-$key (1).exe";  Expect = $key },
        @{ Name = "AstraAgent-Setup.exe";           Expect = ''   },
        @{ Name = "setup.exe";                      Expect = ''   }
    )

    $failed = 0
    $tableReported = $false

    foreach ($case in $selfCases) {
        $named   = Join-Path $work $case.Name
        $results = Join-Path $work "results.txt"
        Copy-Item $testExe $named -Force
        Remove-Item $results -ErrorAction SilentlyContinue

        # /VERYSILENT so no window appears; the build exits on its own regardless.
        $p = Start-Process -FilePath $named -ArgumentList "/VERYSILENT", "/OUT=$results" -Wait -PassThru
        if (-not (Test-Path $results)) {
            Write-Host "FAIL  $($case.Name): the test build wrote no results" -ForegroundColor Red
            $failed++
            continue
        }

        $lines = Get-Content $results
        if (-not $tableReported) {
            # The filename-independent table is identical on every run; show it once.
            $lines | Where-Object { $_ -match '^(PASS|FAIL)\t' } | ForEach-Object {
                $colour = if ($_ -like 'PASS*') { 'DarkGray' } else { 'Red' }
                Write-Host "  $_" -ForegroundColor $colour
            }
            $tableReported = $true
        }

        $tableFailures = [int](($lines | Where-Object { $_ -like "FAILURES`t*" }) -split "`t")[1]
        if ($tableFailures -gt 0) { $failed += $tableFailures }

        $selfLine = $lines | Where-Object { $_ -like "SELF`t*" }
        $got = ''
        if ($selfLine) { $got = ($selfLine -split "`t", 2)[1] }
        if ($got -eq $case.Expect) {
            Write-Host "PASS  srcexe '$($case.Name)' -> [$got]" -ForegroundColor Green
        } else {
            Write-Host "FAIL  srcexe '$($case.Name)' -> got [$got], want [$($case.Expect)]" -ForegroundColor Red
            $failed++
        }
        Remove-Item $named -Force -ErrorAction SilentlyContinue
    }

    Write-Host ""
    if ($failed -gt 0) {
        Write-Host "$failed check(s) FAILED" -ForegroundColor Red
        exit 1
    }
    Write-Host "All key-parsing checks passed." -ForegroundColor Green
    exit 0
}
finally {
    Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
