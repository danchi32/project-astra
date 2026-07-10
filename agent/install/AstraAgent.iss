; ASTRA Agent — Inno Setup installer.
; Compiled by CI (see .github/workflows/agent-installer.yml) into AstraAgentSetup.exe.
; Expects the published, self-contained agent in .\publish (dotnet publish output).
;
; Interactive:  double-click, enter the server URL + enrollment token on the wizard page.
; Silent:       AstraAgentSetup.exe /VERYSILENT /SERVERURL=https://... /TOKEN=abc123

#define AppName "ASTRA Agent"
#define AppVersion "0.1.0"
#define AppPublisher "ASTRA"
#define ServiceName "AstraAgent"
#define ServiceExe "AstraAgent.Service.exe"

[Setup]
AppId={{4B4F1C2A-7A3E-4E9D-9E7B-ASTRA0AGENT01}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Astra\Agent
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=admin
OutputBaseFilename=AstraAgentSetup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName={#AppName}

[Files]
Source: "publish\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Code]
var
  ConfigPage: TInputQueryWizardPage;

function GetServerUrl(): string;
begin
  Result := ExpandConstant('{param:SERVERURL|}');
  if (Result = '') and Assigned(ConfigPage) then
    Result := Trim(ConfigPage.Values[0]);
end;

function GetToken(): string;
begin
  Result := ExpandConstant('{param:TOKEN|}');
  if (Result = '') and Assigned(ConfigPage) then
    Result := Trim(ConfigPage.Values[1]);
end;

function ParamsProvided(): Boolean;
begin
  Result := (ExpandConstant('{param:SERVERURL|}') <> '') and
            (ExpandConstant('{param:TOKEN|}') <> '');
end;

procedure InitializeWizard();
begin
  ConfigPage := CreateInputQueryPage(wpWelcome,
    'ASTRA connection',
    'Point this agent at your ASTRA server.',
    'Enter the server URL and the one-time enrollment token from the portal ' +
    '(Devices -> Install agent). The device enrolls automatically after install.');
  ConfigPage.Add('Server URL (e.g. https://astra.yourco.com):', False);
  ConfigPage.Add('Enrollment token:', False);
  ConfigPage.Values[0] := ExpandConstant('{param:SERVERURL|https://}');
  ConfigPage.Values[1] := ExpandConstant('{param:TOKEN|}');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if Assigned(ConfigPage) and (PageID = ConfigPage.ID) then
    Result := ParamsProvided();
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if Assigned(ConfigPage) and (CurPageID = ConfigPage.ID) then
  begin
    if GetServerUrl() = '' then
    begin
      MsgBox('Please enter the server URL.', mbError, MB_OK);
      Result := False;
    end
    else if GetToken() = '' then
    begin
      MsgBox('Please enter the enrollment token.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure WriteConfig();
var
  Json: string;
  Url: string;
begin
  Url := GetServerUrl();
  { strip any trailing slash }
  if (Length(Url) > 0) and (Url[Length(Url)] = '/') then
    Url := Copy(Url, 1, Length(Url) - 1);
  Json :=
    '{' + #13#10 +
    '  "Astra": {' + #13#10 +
    '    "ServerUrl": "' + Url + '",' + #13#10 +
    '    "EnrollmentToken": "' + GetToken() + '",' + #13#10 +
    '    "HeartbeatIntervalSeconds": 60' + #13#10 +
    '  }' + #13#10 +
    '}' + #13#10;
  SaveStringToFile(ExpandConstant('{app}\appsettings.json'), Json, False);
end;

procedure RunSc(const Args: string);
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\sc.exe'), Args, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ExePath: string;
begin
  if CurStep = ssPostInstall then
  begin
    WriteConfig();
    ExePath := ExpandConstant('{app}\{#ServiceExe}');

    { Idempotent: remove any prior service first. }
    RunSc('stop {#ServiceName}');
    RunSc('delete {#ServiceName}');
    Sleep(1500);

    RunSc('create {#ServiceName} binPath= "' + ExePath + '" start= auto');
    RunSc('description {#ServiceName} "ASTRA endpoint agent - telemetry and secure self-healing."');
    RunSc('failure {#ServiceName} reset= 86400 actions= restart/60000/restart/60000/restart/60000');
    RunSc('start {#ServiceName}');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    RunSc('stop {#ServiceName}');
    RunSc('delete {#ServiceName}');
    Sleep(1000);
  end;
end;
