; Test harness for the installer's enrollment-key parsing.
;
; Compiles keyparse.iss into a throwaway executable that evaluates a table of
; filenames, writes the results to /OUT=, and then returns False from
; InitializeSetup so Setup exits immediately — nothing is extracted, no service is
; touched, nothing is written outside the results file. That is what makes this
; runnable on a developer machine: the real installer cannot be exercised without
; actually installing the agent.
;
; Driven by Run-KeyParseTests.ps1, which also renames the exe to check the
; filename-derived path end to end.

#define KeyPrefix "AstraAgent-Setup-"

[Setup]
AppId={{2C7A9E51-4F63-4D0B-8E22-6A5B1F3C7D94}
AppName=ASTRA key-parse test
AppVersion=0.0.0
DefaultDirName={tmp}\astra-keyparse-test
OutputDir=.
OutputBaseFilename=KeyParse.Test
Compression=none
PrivilegesRequired=lowest
Uninstallable=no

#include "..\keyparse.iss"

[Code]
var
  Report: String;
  Failures: Integer;

{ Every character of the token_urlsafe alphabet exactly once: 64 long like a real key,
  and covering the whole charset IsPlausibleKey validates against.

  Built rather than written as a literal for the same reason as in
  Run-KeyParseTests.ps1 — a 64-character quoted string beside the word "key" is what
  secret scanning is built to catch, and with every character distinct its entropy is
  maximal, so it reads as more credential-like than a genuine key would. }
function SampleKey(): String;
var
  I: Integer;
begin
  Result := '';
  for I := Ord('a') to Ord('z') do Result := Result + Chr(I);
  for I := Ord('A') to Ord('Z') do Result := Result + Chr(I);
  for I := Ord('0') to Ord('9') do Result := Result + Chr(I);
  Result := Result + '_-';
end;

procedure Check(const Name, Got, Want: String);
var
  Status: String;
begin
  if Got = Want then
    Status := 'PASS'
  else
  begin
    Status := 'FAIL';
    Failures := Failures + 1;
  end;
  Report := Report + Status + #9 + Name + #9 + 'got=[' + Got + ']' + #9 + 'want=[' + Want + ']' + #13#10;
end;

function InitializeSetup(): Boolean;
var
  K, OutPath: String;
begin
  Failures := 0;
  Report := '';

  K := SampleKey();
  Check('sample key is 64 chars', IntToStr(Length(K)), '64');

  Check('plain', KeyFromFileName('AstraAgent-Setup-' + K + '.exe'), K);
  Check('no extension', KeyFromFileName('AstraAgent-Setup-' + K), K);
  Check('browser dedup (1)', KeyFromFileName('AstraAgent-Setup-' + K + ' (1).exe'), K);
  Check('browser dedup (12)', KeyFromFileName('AstraAgent-Setup-' + K + ' (12).exe'), K);
  Check('prefix case-insensitive', KeyFromFileName('astraagent-setup-' + K + '.exe'), K);

  Check('no key at all', KeyFromFileName('AstraAgent-Setup.exe'), '');
  Check('key too short', KeyFromFileName('AstraAgent-Setup-abc123.exe'), '');
  Check('wrong prefix', KeyFromFileName('Something-Else-' + K + '.exe'), '');
  { A character outside the token_urlsafe alphabet must be rejected, not escaped:
    this value reaches a generated command line. }
  Check('illegal character', KeyFromFileName('AstraAgent-Setup-' + Copy(K, 1, 63) + '+.exe'), '');
  Check('non-numeric parens kept', KeyFromFileName('AstraAgent-Setup-' + K + ' (x).exe'), '');
  Check('empty parens kept', KeyFromFileName('AstraAgent-Setup-' + K + ' ().exe'), '');
  Check('renamed by hand', KeyFromFileName('setup.exe'), '');

  { The real path: whatever this executable is currently called. }
  Report := Report + 'SELF' + #9 + KeyFromOwnFileName() + #13#10;
  Report := Report + 'FAILURES' + #9 + IntToStr(Failures) + #13#10;

  OutPath := ExpandConstant('{param:OUT|' + ExpandConstant('{tmp}') + '\keyparse-results.txt}');
  SaveStringToFile(OutPath, Report, False);

  { Never proceed — this build exists only to evaluate the functions above. }
  Result := False;
end;
