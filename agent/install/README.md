# Deploying the ASTRA Windows agent

Three scripts cover the full lifecycle. All must run in an **elevated** PowerShell
(Run as Administrator).

| Script | Purpose |
|---|---|
| `Build-AstraAgent.ps1` | Publish a self-contained agent build to distribute. |
| `Install-AstraAgent.ps1` | Install + enroll the agent as a Windows service on a target machine. |
| `Uninstall-AstraAgent.ps1` | Stop, remove the service and clean up. |

## Fastest path — from the portal

1. In the portal go to **Devices → Install agent** (admin only).
2. Enter a label and the server URL the agent should reach, then **Generate installer**.
3. Download the produced `Install-AstraAgent.ps1` — it already has your server URL and a
   one-time enrollment token baked in.
4. On the target machine, alongside a published agent build (`dist` folder — see below),
   run it elevated:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Install-AstraAgent.ps1 -Source .\dist
   ```

The device enrolls on first start and appears under **Devices** within a minute.

## Manual path

### 1. Build a distributable once
```powershell
cd agent\install
.\Build-AstraAgent.ps1 -Zip      # -> dist\ and dist.zip (self-contained, no .NET needed on targets)
```

### 2. Install on each endpoint
Ship `dist\` (or `dist.zip`) and `Install-AstraAgent.ps1` to the machine, then:
```powershell
.\Install-AstraAgent.ps1 -ServerUrl https://astra.example.com -EnrollmentToken <token> -Source .\dist
```
Create the `<token>` in the portal (**Devices → Install agent**) or via
`POST /api/v1/devices/enrollment-tokens`.

On a developer machine with the .NET 8 SDK and this repo checked out you can skip the
build step and publish in place:
```powershell
.\Install-AstraAgent.ps1 -ServerUrl http://localhost:8000 -EnrollmentToken <token> -BuildFromSource
```

## What the installer does

- Removes any prior `AstraAgent` service (idempotent reinstall).
- Copies the binaries to `C:\Program Files\Astra\Agent`.
- Writes `appsettings.json` with the server URL and enrollment token.
- Registers `AstraAgent` as an auto-start service with crash auto-restart and starts it.

The device credential is DPAPI-encrypted at `C:\ProgramData\Astra\agent.credential`; the
enrollment token is only used once, on first enrollment.

## Uninstall
```powershell
.\Uninstall-AstraAgent.ps1
```
