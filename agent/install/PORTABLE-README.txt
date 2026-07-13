ASTRA Agent - Portable Installer
================================

Copy this whole folder to any Windows PC to install the ASTRA agent. The PC will
enroll into your ASTRA portal, send telemetry (device/asset info), and get the
tray chat.

BEFORE YOU START
  Generate an enrollment token in the portal:
    Devices -> Install agent -> enter a label -> Generate enrollment token
    -> expand "Need the raw enrollment token?" -> copy it.
  One token works for every machine until it expires.

INSTALL  (run as Administrator)
  1. Right-click Start -> "Terminal (Admin)" (or "Windows PowerShell (Admin)").
  2. cd into this folder, e.g.:  cd C:\Users\You\Downloads\AstraAgent-Portable
  3. Run (paste your token):
       powershell -ExecutionPolicy Bypass -File .\Install-AstraAgent-Portable.ps1 -EnrollmentToken YOUR_TOKEN

WHAT IT DOES
  - Installs the .NET 8 Desktop Runtime if missing (official Microsoft, signed).
  - Adds a hosts entry so the backend is reachable when corporate DNS can't resolve it.
  - Installs the ASTRA background service (auto-start) + the tray chat (auto-start at
    login), both via the trusted `dotnet` host so antivirus/ASR does not block them.

VERIFY
  - The script prints "AstraAgent ... Running".
  - The device shows ONLINE in the portal within a minute.
  - An "ASTRA Assistant" icon appears in the system tray (its chat).

UNINSTALL  (elevated PowerShell)
  sc.exe stop AstraAgent
  sc.exe delete AstraAgent
  Remove-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -Name AstraAssistant -ErrorAction SilentlyContinue
  Remove-Item "C:\Program Files\Astra" -Recurse -Force

NOTES
  - Override the backend with  -ServerUrl <url>  and  -BackendIp <ip>  if needed.
    Pass  -BackendIp ""  to skip the hosts entry if the machine's DNS already works.
  - This is a test/demo deployment. For a real fleet the durable fix is to code-sign
    the agent and have IT allow the backend hostname (DNS + firewall) rather than
    relying on a hosts-file entry.
