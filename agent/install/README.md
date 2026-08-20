# Deploying the ASTRA Windows agent

The portal hands an admin a ready-to-run installer with their organization's
enrollment key already in it. Two shapes, same agent, same install logic:

| Download | For | How it authenticates |
|---|---|---|
| `AstraAgent-Setup-<ticket>.exe` | One machine at a time — download, double-click | Expiring ticket in the filename |
| `AstraAgent-Portable.zip` | Intune / SCCM / GPO rollouts | Permanent org key, baked into the script inside |

Both install the framework-dependent build and run it through the trusted `dotnet`
host. That indirection is deliberate: it survives locked-down machines where ASR
blocks unsigned executables outright.

## Why the .exe is built once, not per organization

The `.zip` is assembled per request by the backend (`app/services/agent_installer.py`).
The `.exe` cannot be: Inno Setup's compiler is Windows-only and the backend runs on
Linux. So one exe is compiled ahead of time and served **byte-identically** to every
organization, with the credential travelling in the filename it is served under.

Nor can the backend inject a key into the prebuilt exe. Inno verifies a CRC over every
file it packs, so patching a placeholder yields a "corrupted installer"; and appending
to the end would break Authenticode, which is the one thing that actually gets the agent
past Defender. Fixed bytes are the price of being signable, and signing is worth more
than a shorter filename.

### Why a ticket and not the org's enrollment key

A filename is exposed in ways a secret should not be — the downloads folder, browser
history, a shared screen. The org's enrollment key is permanent and unrevocable without
collateral: rotating it kills every `.zip` installer already distributed. So it never
goes in a filename.

Each `.exe` download instead mints its own enrollment ticket (`secrets.token_urlsafe(16)`,
22 characters), which expires after the org's configured token lifetime and can be
revoked on its own — **Get installer → Downloaded .exe installers → Invalidate** — without
touching the key or the `.zip`. A new ticket per download is forced rather than chosen:
only the hash is stored, so an earlier one cannot be recovered and reissued.

If the filename is changed after download the installer asks for a key instead, so a
rename is annoying, never silently broken. `IsPlausibleKey` in `keyparse.iss` accepts
both lengths, since an admin may paste the permanent key by hand.

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
- On managed PCs the `.exe` may not run at all. The ASR rule *Block executable files from
  running unless they meet a prevalence, age, or trusted list criterion*
  (`01443614-CD74-433A-B99E-2ECDC07BFC25`) kills Inno's own temp bootstrap, surfacing as
  **"Unable to execute file in the temporary directory. Error 5: Access is denied."**
  It is deployed by Intune, so it cannot be excluded locally, and Tamper Protection
  prevents working around it. Look for Event ID 1121 in
  *Microsoft-Windows-Windows Defender/Operational* to confirm.
- **Smart App Control**, where enabled, blocks the agent the same way. There is no
  exclusion for SAC — it must be switched off, and Windows will not let it be switched
  back on afterwards.
- Defender occasionally quarantines `AstraAgent.Service.dll`.

**The `.zip` is unaffected by all of this** and is the fallback for such machines: it
launches no new executable, only Windows' own signed `cmd.exe` and `powershell.exe` with
a script as an argument. That was the reason for its design, and it holds up.

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
