# ASTRA Windows Agent

C# .NET 8 Windows Service. See root [CLAUDE.md](../CLAUDE.md) for the security model.

## Current state — Phase 2: Enrollment + Heartbeat

- **Enrollment**: exchanges an admin-issued enrollment token plus device facts (hostname,
  registry MachineGuid, OS version, BIOS serial) for a per-device credential.
- **Credential storage**: DPAPI-encrypted (LocalMachine scope) at
  `C:\ProgramData\Astra\agent.credential` — never plaintext.
- **Heartbeat**: every 60s, reports agent version and the interactive console user
  (resolved via WTS APIs from the service session). Exponential backoff up to 15 min
  when the backend is unreachable; automatic one-shot re-enrollment if the credential
  is rejected (e.g. rotated by a reinstall elsewhere).
- Runs as a Windows Service (`AstraAgent`) or as a plain console app for development.

Planned next: telemetry collectors (Phase 3), tray application, offline queue, remediation executor (Phase 5).

## Build & test

Requires the .NET 8 SDK.

```powershell
cd agent
dotnet build AstraAgent.sln
dotnet test AstraAgent.sln
```

## Run (development)

Configure via `appsettings.json` or environment variables:

```powershell
$env:Astra__ServerUrl = "http://localhost:8000"
$env:Astra__EnrollmentToken = "<token from POST /api/v1/devices/enrollment-tokens>"
dotnet run --project src/AstraAgent.Service
```

On first run the agent enrolls and persists its device credential; the enrollment token
is not needed afterwards.

## Install as a Windows Service

```powershell
dotnet publish src/AstraAgent.Service -c Release -o C:\Program Files\Astra\Agent
sc.exe create AstraAgent binPath= "C:\Program Files\Astra\Agent\AstraAgent.Service.exe" start= auto
sc.exe start AstraAgent
```
