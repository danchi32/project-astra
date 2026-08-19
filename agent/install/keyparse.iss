; Enrollment-key parsing for the ASTRA installer, kept separate so it can be
; exercised on its own — see tests\KeyParse.Test.iss and tests\Run-KeyParseTests.ps1.
;
; The exe is compiled once and served byte-identically to every organization, so
; the per-org enrollment key cannot be baked in. It travels in the filename the
; backend serves the exe under:  AstraAgent-Setup-<key>.exe
;
; Requires KeyPrefix to be #defined by the including script.

[Code]

{ Enrollment keys are secrets.token_urlsafe(48) — 64 characters drawn only from
  A-Z a-z 0-9 _ and -. Validating that charset is not merely a typo check: the key
  is interpolated into a generated command line, and restricting it to this set is
  what makes that safe. Anything outside it is rejected rather than escaped.
  The length bound is deliberately loose so a future change to the key size does
  not silently break every installer already in the field. }
function IsPlausibleKey(const S: String): Boolean;
var
  I: Integer;
  C: Char;
begin
  Result := False;
  if (Length(S) < 32) or (Length(S) > 128) then
    Exit;
  for I := 1 to Length(S) do
  begin
    C := S[I];
    if not (((C >= 'A') and (C <= 'Z')) or
            ((C >= 'a') and (C <= 'z')) or
            ((C >= '0') and (C <= '9')) or
            (C = '_') or (C = '-')) then
      Exit;
  end;
  Result := True;
end;

{ Browsers de-duplicate a repeat download by appending " (1)", " (2)" … to the
  stem. Strip that, or the second copy anyone downloads would fail to find a key
  and fall through to the manual prompt for no good reason. }
function StripDownloadSuffix(const S: String): String;
var
  I, OpenAt: Integer;
begin
  Result := S;
  if (Length(S) < 4) or (S[Length(S)] <> ')') then
    Exit;
  OpenAt := 0;
  for I := Length(S) - 1 downto 1 do
    if S[I] = '(' then
    begin
      OpenAt := I;
      Break;
    end;
  { Require "<stem> (digits)": at least one digit, and a space before the '('. }
  if (OpenAt < 3) or (S[OpenAt - 1] <> ' ') or (OpenAt = Length(S) - 1) then
    Exit;
  for I := OpenAt + 1 to Length(S) - 1 do
    if (S[I] < '0') or (S[I] > '9') then
      Exit;
  Result := Copy(S, 1, OpenAt - 2);
end;

{ Split out from KeyFromOwnFileName so the parsing can be tested against arbitrary
  names without having to rename a real executable for every case. }
function KeyFromFileName(const FileName: String): String;
var
  Name, Prefix: String;
  Dot: Integer;
begin
  Result := '';
  Name := FileName;

  Dot := Length(Name);
  while (Dot > 0) and (Name[Dot] <> '.') do
    Dot := Dot - 1;
  if Dot > 1 then
    Name := Copy(Name, 1, Dot - 1);

  Name := StripDownloadSuffix(Name);

  Prefix := '{#KeyPrefix}';
  if CompareText(Copy(Name, 1, Length(Prefix)), Prefix) <> 0 then
    Exit;

  Name := Copy(Name, Length(Prefix) + 1, MaxInt);
  if IsPlausibleKey(Name) then
    Result := Name;
end;

function KeyFromOwnFileName(): String;
begin
  Result := KeyFromFileName(ExtractFileName(ExpandConstant('{srcexe}')));
end;
