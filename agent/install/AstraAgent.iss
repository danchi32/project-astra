; ASTRA Agent — single-file Windows installer (Inno Setup 6).
;
; Build:  agent\install\Build-Installer.ps1     (stages the payload, then runs ISCC)
; Output: backend\downloads\AstraAgent-Setup.exe
;
; WHY THIS SHAPE
;   The .zip download is generated per organization at request time, with the
;   enrollment key baked into the script inside it. An .exe cannot work that way:
;   the compiler (ISCC) is Windows-only and the backend runs on Linux, so the exe
;   is compiled ONCE and every organization is served the exact same bytes.
;
;   That is also precisely what Authenticode needs — a signature covers fixed
;   bytes — so the same constraint that forces this design today is the one that
;   makes signing a drop-in later. The credential therefore has to arrive from
;   OUTSIDE the file. It does, in the file's own name:
;
;       AstraAgent-Setup-<enrollment ticket>.exe
;
;   A *ticket*, not the organization's enrollment key. A filename is exposed in
;   ways a secret should not be — the downloads folder, browser history, a shared
;   screen — and that key is permanent, so recovering from a leak would mean
;   rotating it and breaking every .zip installer already distributed. The backend
;   mints a fresh, expiring, individually revocable ticket for each download
;   instead; this script reads it back out of the name. If the name carries nothing
;   usable (renamed by hand, say), the wizard asks rather than installing an agent
;   that could never enrol.
;
;   Silent/managed deployment:
;       AstraAgent-Setup.exe /VERYSILENT /KEY=<ticket or enrollment key>
;
; The install itself is NOT reimplemented here. Install-AstraAgent.ps1 — the same
; script the .zip ships, staged from the single source of truth in
; backend/app/services/agent_installer.py — does the work, so the exe and the zip
; can never drift apart in behaviour.

#define AppName        "ASTRA Agent"
#define AppPublisher   "Technomate AI"
#define ServiceName    "AstraAgent"
#define DefaultServer  "https://api.astra.technomateai.com"
#define KeyPrefix      "AstraAgent-Setup-"

; Build-Installer.ps1 passes /DAgentVersion=... ; this is only the fallback.
#ifndef AgentVersion
  #define AgentVersion "0.0.0"
#endif

[Setup]
AppId={{8F3C61D4-6B2A-4E57-9A18-2D7E4C0B93A5}
AppName={#AppName}
AppVersion={#AgentVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AgentVersion}
VersionInfoDescription={#AppName} installer

; The payload scripts install into {app}\Agent and {app}\Tray, so {app} is the
; parent — this is where the uninstaller and its script live.
DefaultDirName={autopf}\Astra
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=..\..\backend\downloads
OutputBaseFilename=AstraAgent-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\Agent\AstraAgent.Service.dll

; Code signing is not wired up yet (see docs). Build-Installer.ps1 defines SIGN and
; passes /Sastra=<command> once a certificate exists; until then this compiles to an
; unsigned exe and nothing here needs to change when that day comes.
#ifdef SIGN
SignTool=astra
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; The agent payload is staged, not installed, because Install-AstraAgent.ps1 owns
; the copy into Program Files (it must first stop the service and clear the old
; directory — see the comments in that script).
; No deleteafterinstall: that flag's timing relative to ssPostInstall (where the
; install script runs, below) is not something to bet the payload on. {tmp} is
; removed wholesale when Setup exits, which cleans up regardless and unambiguously.
Source: "payload\dist-fd\*";  DestDir: "{tmp}\astra\dist-fd";  Flags: recursesubdirs createallsubdirs ignoreversion
Source: "payload\dist-tray\*"; DestDir: "{tmp}\astra\dist-tray"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "payload\Install-AstraAgent.ps1"; DestDir: "{tmp}\astra"; Flags: ignoreversion
; The uninstaller script persists — Add/Remove Programs calls it below.
Source: "payload\Uninstall-AstraAgent.ps1"; DestDir: "{app}"; Flags: ignoreversion

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\Uninstall-AstraAgent.ps1"""; \
  Flags: runhidden waituntilterminated; RunOnceId: "AstraAgentUninstall"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\Agent"
Type: filesandordirs; Name: "{app}\Tray"
Type: dirifempty;     Name: "{app}"

; Key parsing lives in its own file so it can be tested without installing
; anything — see tests\Run-KeyParseTests.ps1.
#include "keyparse.iss"

[Code]
var
  KeyPage: TInputQueryWizardPage;
  ResolvedKey: String;

function ServerUrl(): String;
begin
  Result := Trim(ExpandConstant('{param:SERVERURL|{#DefaultServer}}'));
  while (Length(Result) > 0) and (Result[Length(Result)] = '/') do
    Result := Copy(Result, 1, Length(Result) - 1);
end;

{ Command line wins, then the filename. Both are resolved before the wizard is
  built so the key page can be skipped entirely when we already know the key. }
function PresetKey(): String;
begin
  Result := Trim(ExpandConstant('{param:KEY|}'));
  if (Result <> '') and not IsPlausibleKey(Result) then
    Result := '';
  if Result = '' then
    Result := KeyFromOwnFileName();
end;

{ Resolved here, not in InitializeWizard: this runs in every mode, whereas the
  wizard is a UI concern and a /VERYSILENT install must still find its key. }
function InitializeSetup(): Boolean;
begin
  ResolvedKey := PresetKey();
  Result := True;
end;

procedure InitializeWizard();
begin
  KeyPage := CreateInputQueryPage(wpWelcome,
    'Enrollment key',
    'Connect this PC to your ASTRA organization.',
    'Paste the enrollment key from the portal (Get installer). Normally the key ' +
    'travels in the installer''s filename and this page is skipped — you are ' +
    'seeing it because the file was renamed after download.');
  KeyPage.Add('Enrollment key:', False);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if Assigned(KeyPage) and (PageID = KeyPage.ID) then
    Result := (ResolvedKey <> '');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Entered: String;
begin
  Result := True;
  if Assigned(KeyPage) and (CurPageID = KeyPage.ID) then
  begin
    Entered := Trim(KeyPage.Values[0]);
    if Entered = '' then
    begin
      MsgBox('Please paste the enrollment key from the ASTRA portal.', mbError, MB_OK);
      Result := False;
    end
    else if not IsPlausibleKey(Entered) then
    begin
      MsgBox('That does not look like an enrollment key. Copy it again from the ' +
             'portal''s Get installer page — it is a single long word with no spaces.',
             mbError, MB_OK);
      Result := False;
    end
    else
      ResolvedKey := Entered;
  end;
end;

{ A silent install has no wizard to prompt on, so an absent key has to fail loudly
  here rather than install an agent that can never enrol. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if (ResolvedKey = '') and (WizardSilent()) then
    Result := 'No enrollment key. Pass /KEY=<key>, or keep the installer''s ' +
              'original filename (' + '{#KeyPrefix}' + '<key>.exe).';
end;

procedure RunInstallScript();
var
  LogDir, LogPath, Runner, Cmd: String;
  Rc: Integer;
begin
  LogDir  := ExpandConstant('{commonappdata}\Astra');
  LogPath := LogDir + '\install-log.txt';
  ForceDirectories(LogDir);

  { Driving PowerShell through a generated .cmd rather than assembling one long
    quoted string for cmd /C: the nested quoting is otherwise very easy to get
    subtly wrong, and this leaves a readable artefact next to the log when an
    install has to be diagnosed on someone else's machine. }
  Runner := ExpandConstant('{tmp}\astra\run-install.cmd');
  Cmd :=
    '@echo off' + #13#10 +
    'chcp 65001 >nul' + #13#10 +
    '"' + ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe') + '"' +
    ' -NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{tmp}\astra\Install-AstraAgent.ps1') + '"' +
    ' -EnrollmentToken "' + ResolvedKey + '"' +
    ' -ServerUrl "' + ServerUrl() + '"' +
    ' -ServiceSrc "' + ExpandConstant('{tmp}\astra\dist-fd') + '"' +
    ' -TraySrc "' + ExpandConstant('{tmp}\astra\dist-tray') + '"' +
    ' >"' + LogPath + '" 2>&1' + #13#10 +
    'exit /b %errorlevel%' + #13#10;

  if not SaveStringToFile(Runner, Cmd, False) then
  begin
    MsgBox('Could not write the installer helper to the temp folder.', mbCriticalError, MB_OK);
    Exit;
  end;

  if not Exec(Runner, '', ExpandConstant('{tmp}\astra'), SW_HIDE, ewWaitUntilTerminated, Rc) then
    Rc := -1;

  if Rc <> 0 then
    { The PowerShell script already explains the common causes (missing .NET
      runtime, antivirus holding a file, an unreachable backend); repeating them
      here would only go stale, so point at its transcript instead. }
    SuppressibleMsgBox(
      'The ASTRA agent did not finish installing (code ' + IntToStr(Rc) + ').' + #13#10#13#10 +
      'What went wrong is written to:' + #13#10 + LogPath,
      mbCriticalError, MB_OK, IDOK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RunInstallScript();
end;
