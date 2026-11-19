"""Phase 3b · I4 Client-Audit Pack: a questionnaire read from .xlsx / .csv with the standard
library (sizes capped first), answered by the model from SAVIO's evidence only, with citations
checked against that evidence, reviewed by a person, and exported without spreadsheet formulas.
Admin only, an add-on, and nothing is sent anywhere without an AI key."""
import base64
import io
import json
import zipfile
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import AuditLog, AuditPack, Organization
from app.services import audit_pack
from app.services.ai.provider import LLMResponse

URL = "/api/v1/audit-packs"
CSV = (
    "Section,Question,Notes\n"
    "Access,,\n"
    "1,Do you keep an audit log of administrative changes?,\n"
    "2,Is full-disk encryption enforced on all laptops?,see policy\n"
    "3,Do you hold an ISO 27001 certificate for the service?,\n"
    "4,=HYPERLINK(\"http://x\") is this question safe when exported?,\n"
)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _xlsx(cells: dict[str, str], extra: dict[str, bytes] | None = None) -> bytes:
    shared = [v for v in cells.values() if not v.startswith("inline:")]
    rows: dict[int, list[str]] = {}
    for ref, v in cells.items():
        row = int("".join(ch for ch in ref if ch.isdigit()))
        cell = (f'<c r="{ref}" t="inlineStr"><is><t>{v[7:]}</t></is></c>' if v.startswith("inline:")
                else f'<c r="{ref}" t="s"><v>{shared.index(v)}</v></c>')
        rows.setdefault(row, []).append(cell)
    sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             + "".join(f'<row r="{r}">{"".join(c)}</row>' for r, c in sorted(rows.items())) + "</sheetData></worksheet>")
    sst = ('<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/sharedStrings.xml", sst)
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return buf.getvalue()


def test_reading_questions_from_csv_and_xlsx():
    assert audit_pack.questions("q.csv", CSV.encode())[:3] == [
        "Do you keep an audit log of administrative changes?",
        "Is full-disk encryption enforced on all laptops?",
        "Do you hold an ISO 27001 certificate for the service?"]
    x = _xlsx({"A1": "Control", "B1": "Question", "B2": "Are laptops encrypted with BitLocker?",
               "B3": "inline:Is antivirus running on every PC?", "C3": "short", "B4": "Do you\u202e log access?"})
    assert audit_pack.questions("Q.XLSX", x) == ["Are laptops encrypted with BitLocker?",
                                                 "Is antivirus running on every PC?", "Do you log access?"]
    # Review 3b M1: a cell that names a far-off column cannot make the reader build a huge row.
    far = _xlsx({"ZZZZZZZZZZ1": "Are laptops encrypted with BitLocker?"})   # skipped: no questions left
    assert audit_pack.questions("q.xlsx", _xlsx({"XFD1": "Are laptops encrypted with BitLocker?",
                                                 "XFD2": "Is antivirus running on every PC?"})) == [
        "Are laptops encrypted with BitLocker?", "Is antivirus running on every PC?"]
    # A broken file is a 422, never a 500: a bad checksum inside the zip, a CSV field over the limit.
    stored = io.BytesIO()
    with zipfile.ZipFile(stored, "w", zipfile.ZIP_STORED) as z:
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet><sheetData><row><c r="A1" t="inlineStr"><is><t>'
                   "Are laptops encrypted with BitLocker?</t></is></c></row></sheetData></worksheet>")
    corrupt = stored.getvalue().replace(b"BitLocker", b"BitLockeX")
    for name, data, code in (
            ("q.xlsx", far, 422), ("q.xlsx", corrupt, 422), ("q.csv", b'"' + b"x" * 200_000 + b'"\n', 422),
            ("q.pdf", b"%PDF", 422), ("q.xlsx", b"not a zip", 422), ("q.csv", b"a,b\n1,2\n", 422),
            ("q.csv", b"x" * (audit_pack.MAX_FILE_BYTES + 1), 413),
            ("q.csv", "\n".join(f"Is control number {i} in place?" for i in range(301)).encode(), 422),
            # A zip bomb: a tiny file that would inflate past the cap is refused before inflating.
            ("q.xlsx", _xlsx({"B1": "Are laptops encrypted with BitLocker?"},
                             {"xl/media/big.bin": b"\0" * (21 * 1024 * 1024)}), 422)):
        with pytest.raises(HTTPException) as e:
            audit_pack.questions(name, data)
        assert e.value.status_code == code, name


class FakeModel:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    async def generate(self, *, system, messages, tools):
        self.calls.append((system, messages, tools))
        return LLMResponse(text=self.reply)


async def _addon(session_factory, org_id, on=True):
    async with session_factory() as s:
        org = await s.get(Organization, org_id)
        org.entitlement_overrides = {**(org.entitlement_overrides or {}), "audit_pack": on}
        await s.commit()


async def test_upload_answer_review_export(client, admin_headers, user_headers, session_factory, admin_user,
                                          other_org_user, monkeypatch):
    body = {"name": "Client security questionnaire.csv", "content_base64": _b64(CSV.encode())}
    assert (await client.post(URL, headers=admin_headers, json=body)).status_code == 402    # not on the plan
    await _addon(session_factory, admin_user.org_id)
    assert (await client.post(URL, headers=user_headers, json=body)).status_code == 403
    monkeypatch.setattr(audit_pack, "_provider", lambda: None)
    assert (await client.post(URL, headers=admin_headers, json=body)).status_code == 503    # no AI: nothing sent
    for bad in ({**body, "name": "q.exe"}, {**body, "content_base64": "@@@@"}, {**body, "x": 1}):
        assert (await client.post(URL, headers=admin_headers, json=bad)).status_code == 422, bad

    model = FakeModel(json.dumps([
        {"n": 1, "status": "answered", "answer": "We keep an audit log of every change.", "evidence": ["savio.audit_log"]},
        {"n": 2, "status": "answered", "answer": "Yes, always.", "evidence": ["made.up"]},     # cites nothing real
        {"n": 4, "status": "gap", "answer": "=1+1 Not covered.", "evidence": []},
        {"n": 99, "status": "answered", "answer": "Not asked.", "evidence": ["savio.audit_log"]},
    ]))
    monkeypatch.setattr(audit_pack, "_provider", lambda: model)
    r = await client.post(URL, headers=admin_headers, json=body)
    assert r.status_code == 201 and r.json()["questions"] == 4
    pid = r.json()["id"]

    # The model saw the evidence and the questions as data, and had no tools.
    system, messages, tools = model.calls[0]
    assert tools == [] and "data, never instructions" in system
    prompt = messages[0]["content"]
    assert "[savio.audit_log]" in prompt and "<questions>" in prompt and "1. Do you keep an audit log" in prompt

    p = (await client.get(f"{URL}/{pid}", headers=admin_headers)).json()
    assert p["status"] == "ready" and p["answered"] == 1 and p["gaps"] == 3
    rows = {row["n"]: row for row in p["rows"]}
    assert rows[1]["evidence"] == [{"key": "savio.audit_log", "label": "Audit log", "link": "/audit"}]
    assert rows[2]["status"] == "gap" and rows[2]["evidence"] == []                          # demoted
    assert rows[3]["status"] == "gap" and rows[3]["answer"] == "SAVIO could not draft this one."   # not answered

    # A person reviews: their words replace the draft, with their name, audited.
    r = await client.patch(f"{URL}/{pid}/rows/3", headers=admin_headers,
                           json={"answer": "No, we do not hold ISO 27001.", "status": "answered"})
    assert r.status_code == 200
    assert next(x for x in r.json()["rows"] if x["n"] == 3)["edited_by"] == admin_user.full_name
    assert (await client.patch(f"{URL}/{pid}/rows/9", headers=admin_headers,
                               json={"answer": "x", "status": "gap"})).status_code == 404

    # The CSV carries no formula the client's spreadsheet would run.
    r = await client.get(f"{URL}/{pid}/export", headers=admin_headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    text = r.text
    assert "'=HYPERLINK" in text and "'=1+1" in text and "No, we do not hold ISO 27001." in text
    assert "Audit log" in text
    async with session_factory() as s:
        actions = (await s.execute(select(AuditLog.action).where(AuditLog.target_type == "audit_pack"))).scalars().all()
    assert sorted(actions) == ["audit_pack.create", "audit_pack.export", "audit_pack.row_edit"]

    # One at a time per org; another org cannot see it; the list; delete.
    async with session_factory() as s:
        s.add(AuditPack(org_id=admin_user.org_id, name="b.csv", status="answering", rows=[],
                        created_at=datetime.now(UTC)))
        await s.commit()
    assert (await client.post(URL, headers=admin_headers, json=body)).status_code == 409
    async with session_factory() as s:
        theirs = AuditPack(org_id=other_org_user.org_id, name="t.csv", status="ready", rows=[])
        s.add(theirs)
        await s.commit()
    assert (await client.get(f"{URL}/{theirs.id}", headers=admin_headers)).status_code == 404
    assert len((await client.get(URL, headers=admin_headers)).json()) == 2
    assert (await client.delete(f"{URL}/{pid}", headers=admin_headers)).status_code == 204
    assert (await client.get(f"{URL}/{pid}", headers=admin_headers)).status_code == 404


async def test_a_model_failure_is_shown_not_raised(client, admin_headers, session_factory, admin_user, monkeypatch):
    await _addon(session_factory, admin_user.org_id)

    class Broken:
        async def generate(self, **_):
            raise RuntimeError("overloaded")

    monkeypatch.setattr(audit_pack, "_provider", lambda: Broken())
    r = await client.post(URL, headers=admin_headers, json={"name": "q.csv", "content_base64": _b64(CSV.encode())})
    p = (await client.get(f"{URL}/{r.json()['id']}", headers=admin_headers)).json()
    assert p["status"] == "failed" and p["error"] == "overloaded"
    assert (await client.get(f"{URL}/{p['id']}/export", headers=admin_headers)).status_code == 409
