# Deploying the ASTRA Windows agent

The portal hands an admin a ready-to-run installer with their organization's
enrollment key already in it. Two shapes, same agent, same install logic:

| Download | For | How the key gets in |
|---|---|---|
| `AstraAgent-Setup-<key>.exe` | One machine at a time — download, double-click | The filename |
| `AstraAgent-Portable.zip` | Intune / SCCM / GPO rollouts | Baked into the script inside |

Both install the framework-dependent build and run it through the trusted `dotnet`
host. That indirection is deliberate: it survives locked-down machines where ASR
blocks unsigned executables outright.

## Why the .exe is built once, not per organization

The `.zip` is assembled per request by the backend (`app/services/agent_installer.py`).
The `.exe` cannot be: Inno Setup's compiler is Windows-only and the backend runs on
Linux. So one exe is compiled ahead of time and served **byte-identically** to every
organization, with the key travelling in the filename it is served under.

That is also exactly what Authenticode needs — a signature covers fixed bytes — so the
constraint that forces this design is the same one that makes signing a drop-in later.

If the filename is changed after download the installer asks for the key instead, so a
rename is annoying, never silently broken.

## Building the .exe

Needs the [Inno Setup 6](https://jrsoftware.org) compiler
(`winget install --id JRSoftware.InnoSetup`) and Python.

```powershell
cd agent\install
.\Build-Installer.ps1
```

Produces `backend\downloads\AstraAgent-Setup.exe` plus `AstraAgent-Setup.json`, both of
which are committed — the backend serves the exe out of the image and reads the sidecar
to check the exe was built for **this** deployment before offering it. An exe built for
another backend is refused rather than handed out, since its agents would enrol
somewhere else.

Rebuild whenever `backend/downloads/agent-portable.zip` or the install script changes;
the payload is staged from those, so the exe and the zip cannot drift apart.

For a non-production backend:

```powershell
.\Build-Installer.ps1 -ServerUrl https://staging.example.com
```

### Tests

```powershell
.\tests\Run-KeyParseTests.ps1
```

Compiles a throwaway build that only evaluates the filename→key parsing and exits, then
runs it under a set of filenames. Installs nothing.

## Code signing — not done yet

The binaries are **unsigned**, which is why:

- SmartScreen shows *"Windows protected your PC"* on first run (More info → Run anyway).
- **Smart App Control**, where enabled, blocks the agent outright. There is no exclusion
  for SAC — it has to be switched off on that machine, and Windows will not let it be
  switched back on afterwards.
- Defender occasionally quarantines `AstraAgent.Service.dll`.

A certificate fixes all three at once. Nothing in the build needs restructuring for it:

```powershell
.\Build-Installer.ps1 -SignCommand 'signtool.exe sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /f cert.pfx /p <pw> $f'
```

`$f` is Inno Setup's placeholder for the file being signed. The build signs the two
agent DLLs first (those are what SAC and Defender judge) and then the setup exe itself.
`$env:ASTRA_SIGNTOOL` works as a default so CI need not pass the flag.

## Uninstall

From **Add/Remove Programs**, or:

```powershell
.\Uninstall-AstraAgent.ps1
```

The portal also offers this as a standalone download for machines installed from the
zip, which leaves no Add/Remove Programs entry.

## What an install actually does

- Installs the .NET 8 Desktop Runtime if missing (official Microsoft build, signed).
- Tears down any previous `AstraAgent` service, waiting for the hosting process to die —
  `sc delete` alone leaves the DLL locked and the next install fails.
- Clears `C:\Program Files\Astra\Agent` before copying, so stale files from an older
  version cannot make the .NET host load a mismatched assembly.
- Writes `appsettings.json` with the server URL and enrollment key.
- Registers `AstraAgent` as an auto-start service with crash auto-restart.
- Installs the tray chat and starts it **in the signed-in user's session**, not the
  installing admin's.

The device credential is DPAPI-encrypted at `C:\ProgramData\Astra\agent.credential`. An
install transcript is written to `C:\ProgramData\Astra\install-log.txt` — the first place
to look when a machine will not enrol.

## Legacy scripts

Kept for reference; not used by anything the portal ships:

| Script | Was |
|---|---|
| `Build-AstraAgent.ps1` | Self-contained (~34 MB) publish, before the framework-dependent switch |
| `Install-AstraAgent.ps1` | Installer for that build; registers the raw `.exe` as a service, which is what ASR blocks |
| `Install-Local-DotnetHost.ps1` | Developer-machine install straight from a local build |
