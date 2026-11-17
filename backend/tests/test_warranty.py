"""L5b · Warranty provenance and CSV import. The rule under test: a found date never silently
replaces one a person entered; it waits beside it until an admin picks."""
from sqlalchemy import select

from app.models import Asset, AssetCategory, AssetEvent, AuditLog


async def _asset(session_factory, org_id, name, **kw):
    async with session_factory() as s:
        a = Asset(org_id=org_id, name=name, category=AssetCategory.LAPTOP, **kw)
        s.add(a)
        await s.commit()
        return a.id


async def _get(session_factory, asset_id):
    async with session_factory() as s:
        return await s.get(Asset, asset_id)


async def _import(client, headers, text):
    return await client.post("/api/v1/assets/warranty/import", headers=headers, json={"csv": text})


async def test_csv_import_fills_blanks_and_never_overwrites_a_persons_date(
        client, admin_headers, session_factory, admin_user, other_org):
    org = admin_user.org_id
    blank = await _asset(session_factory, org, "Blank", serial_number="SN-1")
    manual = await _asset(session_factory, org, "Manual", asset_tag="TAG-2",
                          warranty_expiry="2026-01-01", warranty_source="manual")
    legacy = await _asset(session_factory, org, "Legacy", serial_number="SN-3", warranty_expiry="2026-05-05")
    same = await _asset(session_factory, org, "Same", serial_number="SN-4", warranty_expiry="2027-01-01",
                        warranty_source="csv")
    from_csv = await _asset(session_factory, org, "Old CSV", serial_number="SN-5",
                            warranty_expiry="2025-01-01", warranty_source="csv")
    theirs = await _asset(session_factory, other_org.id, "Not ours", serial_number="SN-9")

    r = await _import(client, admin_headers, "\n".join([
        "Serial_Number,asset_tag,warranty_expiry",
        "sn-1,,2027-03-31",            # case-insensitive serial
        ",TAG-2,31/12/2027",           # day-first date, a person's date: conflict
        "SN-3,,2028-01-01",            # dated before sources existed: still a person's
        "SN-4,,2027-01-01",            # same date
        "SN-5,,2029-06-30",            # an earlier import's date may be updated
        "SN-9,,2027-01-01",            # another org's serial: invisible
        "SN-1,,not a date",
        ",,2027-01-01",
    ]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["rows"], body["updated"], body["unchanged"], body["conflicts"]) == (8, 2, 1, 2)
    assert body["unmatched"] == ["SN-9"] and len(body["invalid"]) == 2

    a = await _get(session_factory, blank)
    assert (a.warranty_expiry, a.warranty_source) == ("2027-03-31", "csv") and a.warranty_checked_at
    m = await _get(session_factory, manual)
    assert (m.warranty_expiry, m.warranty_found, m.warranty_found_source) == ("2026-01-01", "2027-12-31", "csv")
    assert (await _get(session_factory, legacy)).warranty_expiry == "2026-05-05"
    assert (await _get(session_factory, legacy)).warranty_found == "2028-01-01"
    assert (await _get(session_factory, from_csv)).warranty_expiry == "2029-06-30"
    assert (await _get(session_factory, theirs)).warranty_expiry is None

    async with session_factory() as s:
        notes = [e.note for e in (await s.execute(select(AssetEvent).where(AssetEvent.asset_id == blank))).scalars()]
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "asset.warranty_import"))).scalars().one()
    assert any("2027-03-31" in (n or "") for n in notes)
    assert audit.detail["conflicts"] == 2


async def test_admin_picks_between_the_two_dates(client, admin_headers, session_factory, admin_user):
    org = admin_user.org_id
    take = await _asset(session_factory, org, "Take", serial_number="T-1",
                        warranty_expiry="2026-01-01", warranty_source="manual")
    keep = await _asset(session_factory, org, "Keep", serial_number="T-2",
                        warranty_expiry="2026-01-01", warranty_source="manual")
    await _import(client, admin_headers, "serial,warranty_expiry\nT-1,2028-02-02\nT-2,2028-02-02")

    r = await client.post(f"/api/v1/assets/{take}/warranty/resolve", headers=admin_headers, json={"keep": "found"})
    assert r.status_code == 200, r.text
    assert (r.json()["warranty_expiry"], r.json()["warranty_source"], r.json()["warranty_found"]) == (
        "2028-02-02", "csv", None)
    r = await client.post(f"/api/v1/assets/{keep}/warranty/resolve", headers=admin_headers, json={"keep": "current"})
    assert (r.json()["warranty_expiry"], r.json()["warranty_found"]) == ("2026-01-01", None)
    again = await client.post(f"/api/v1/assets/{keep}/warranty/resolve", headers=admin_headers, json={"keep": "found"})
    assert again.status_code == 409


async def test_a_date_typed_by_hand_is_marked_manual(client, admin_headers, session_factory, admin_user):
    r = await client.post("/api/v1/assets", headers=admin_headers, json={
        "name": "New laptop", "category": "laptop", "warranty_expiry": "2027-07-07"})
    assert r.json()["warranty_source"] == "manual"
    asset_id = r.json()["id"]

    # A pending found date is settled by typing a date.
    async with session_factory() as s:
        a = await s.get(Asset, asset_id)
        a.warranty_found, a.warranty_found_source = "2030-01-01", "csv"
        await s.commit()
    r = await client.patch(f"/api/v1/assets/{asset_id}", headers=admin_headers, json={"warranty_expiry": "2027-08-08"})
    assert (r.json()["warranty_source"], r.json()["warranty_found"]) == ("manual", None)
    r = await client.patch(f"/api/v1/assets/{asset_id}", headers=admin_headers, json={"warranty_expiry": None})
    assert r.json()["warranty_source"] is None


INVOICE = {"media_type": "application/pdf", "data_b64": "JVBERi0xLjQK"}


def _fake_read(fields):
    from app.services.invoice_reader import InvoiceFields

    async def read_invoice(*, data_b64, media_type):
        return InvoiceFields(**fields)
    return read_invoice


async def test_invoice_fills_warranty_and_purchase(client, admin_headers, session_factory, admin_user, monkeypatch):
    from app.services import invoice_reader

    blank = await _asset(session_factory, admin_user.org_id, "Acer Aspire", serial_number="ACR-77")
    monkeypatch.setattr(invoice_reader, "read_invoice", _fake_read({
        "vendor": "Croma", "invoice_date": "20/03/2026", "warranty_end": None, "warranty_months": 12,
        "total_cost": 55000, "serial_numbers": ["acr-77"]}))
    r = await client.post(f"/api/v1/assets/{blank}/warranty/invoice", headers=admin_headers, json=INVOICE)
    assert r.status_code == 200, r.text
    assert r.json() == {"result": "set", "warranty_found": "2027-03-20", "filled": ["purchase date", "purchase cost"],
                        "vendor": "Croma", "invoice_date": "2026-03-20"}
    a = await _get(session_factory, blank)
    assert (a.warranty_expiry, a.warranty_source, a.purchase_date, a.purchase_cost) == (
        "2027-03-20", "invoice_ai", "2026-03-20", 55000.0)
    async with session_factory() as s:
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "asset.warranty_invoice"))).scalars().one()
    assert "JVBER" not in str(audit.detail)          # the file never reaches the audit log


async def test_invoice_respects_people_and_serials(client, admin_headers, session_factory, admin_user, monkeypatch):
    from app.services import invoice_reader

    manual = await _asset(session_factory, admin_user.org_id, "Typed", serial_number="M-1",
                          warranty_expiry="2026-06-01", warranty_source="manual", purchase_date="2025-06-01")
    monkeypatch.setattr(invoice_reader, "read_invoice", _fake_read({
        "vendor": None, "invoice_date": "2025-06-01", "warranty_end": "2027-06-01", "warranty_months": None,
        "total_cost": None, "serial_numbers": []}))
    r = await client.post(f"/api/v1/assets/{manual}/warranty/invoice", headers=admin_headers, json=INVOICE)
    assert (r.json()["result"], r.json()["filled"]) == ("conflict", [])
    assert (await _get(session_factory, manual)).warranty_expiry == "2026-06-01"

    monkeypatch.setattr(invoice_reader, "read_invoice", _fake_read({
        "vendor": "X", "invoice_date": None, "warranty_end": "2028-01-01", "warranty_months": None,
        "total_cost": None, "serial_numbers": ["OTHER-9"]}))
    wrong = await client.post(f"/api/v1/assets/{manual}/warranty/invoice", headers=admin_headers, json=INVOICE)
    assert wrong.status_code == 400 and "OTHER-9".lower() in wrong.json()["detail"].lower()

    monkeypatch.setattr(invoice_reader, "read_invoice", _fake_read({
        "vendor": "X", "invoice_date": None, "warranty_end": None, "warranty_months": None,
        "total_cost": None, "serial_numbers": []}))
    none = await client.post(f"/api/v1/assets/{manual}/warranty/invoice", headers=admin_headers, json=INVOICE)
    assert none.json()["result"] == "not_stated"


async def test_invoice_without_ai_or_with_a_bad_type(client, admin_headers, user_headers, session_factory, admin_user):
    a = await _asset(session_factory, admin_user.org_id, "Any")
    r = await client.post(f"/api/v1/assets/{a}/warranty/invoice", headers=admin_headers, json=INVOICE)
    assert r.status_code == 503                       # no API key in tests
    bad = await client.post(f"/api/v1/assets/{a}/warranty/invoice", headers=admin_headers,
                            json={"media_type": "text/html", "data_b64": "PGgxPg=="})
    assert bad.status_code == 422
    assert (await client.post(f"/api/v1/assets/{a}/warranty/invoice", headers=user_headers,
                              json=INVOICE)).status_code == 403


async def test_the_request_the_real_sdk_sends(monkeypatch):
    """Through the installed Anthropic SDK, with only the HTTP transport faked: the file goes as
    a document block, the answer is held to a JSON schema, the refusal fallback is on, and
    the client is bounded. A refusal, or an answer that is not the fields, is reported."""
    import json as _json

    import httpx2 as httpx      # the Anthropic SDK 2.x transport package
    import pytest

    from app.core.config import get_settings
    from app.services import invoice_reader

    seen = {}
    reply = {"stop_reason": "end_turn", "text": _json.dumps({
        "vendor": "Dell", "invoice_date": "2026-01-31", "warranty_end": None, "warranty_months": 36,
        "total_cost": 80000, "serial_numbers": ["ABC"]})}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = _json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta")
        return httpx.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": reply["text"]}], "stop_reason": reply["stop_reason"],
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}})

    real = invoice_reader.anthropic.AsyncAnthropic
    built = {}

    def client(**kw):
        built.update(kw)
        return real(**kw, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    monkeypatch.setattr(invoice_reader.anthropic, "AsyncAnthropic", client)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-key-not-real")
    fields = await invoice_reader.read_invoice(data_b64="JVBERi0=", media_type="application/pdf")
    assert (fields.warranty_months, fields.total_cost) == (36, 80000)
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5" and body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["beta"]
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["messages"][0]["content"][0]["type"] == "document"
    assert (built["timeout"], built["max_retries"]) == (60, 1)

    reply["stop_reason"] = "refusal"
    with pytest.raises(invoice_reader.InvoiceReadError):
        await invoice_reader.read_invoice(data_b64="JVBERi0=", media_type="application/pdf")
    reply["stop_reason"] = "end_turn"
    for bad in ('{"vendor": null, "invoice_date": null, "warranty_end": null, "warranty_months": null, '
                '"total_cost": Infinity, "serial_numbers": []}', '["not", "an", "object"]',
                '{"vendor": "x", "extra": 1}'):
        reply["text"] = bad
        with pytest.raises(invoice_reader.InvoiceReadError):
            await invoice_reader.read_invoice(data_b64="JVBERi0=", media_type="application/pdf")


async def test_invoice_reads_are_limited_and_all_counted(
        client, admin_headers, session_factory, admin_user, monkeypatch):
    """Each read is a paid call: limited per person per hour, and every attempt counts,
    including one that then fails."""
    from app.services import invoice_reader, warranty
    from app.services.invoice_reader import InvoiceReadError

    a = await _asset(session_factory, admin_user.org_id, "Any")

    async def failing(*, data_b64, media_type):
        raise InvoiceReadError("The AI service declined to read that file.")

    monkeypatch.setattr(invoice_reader, "read_invoice", failing)
    monkeypatch.setattr(warranty, "MAX_INVOICES_PER_USER_HOUR", 2)
    url = f"/api/v1/assets/{a}/warranty/invoice"
    assert [(await client.post(url, headers=admin_headers, json=INVOICE)).status_code for _ in range(3)] == [422, 422, 409]
    async with session_factory() as s:
        reads = (await s.execute(select(AuditLog).where(AuditLog.action == "asset.warranty_invoice_read"))).scalars().all()
    assert len(reads) == 2


async def test_an_invoice_never_replaces_an_imported_date(client, admin_headers, session_factory, admin_user, monkeypatch):
    from app.services import invoice_reader

    imported = await _asset(session_factory, admin_user.org_id, "Imported", warranty_expiry="2027-01-01",
                            warranty_source="csv")
    monkeypatch.setattr(invoice_reader, "read_invoice", _fake_read({
        "vendor": None, "invoice_date": None, "warranty_end": "2030-01-01", "warranty_months": None,
        "total_cost": None, "serial_numbers": []}))
    r = await client.post(f"/api/v1/assets/{imported}/warranty/invoice", headers=admin_headers, json=INVOICE)
    assert r.json()["result"] == "conflict"
    a = await _get(session_factory, imported)
    assert (a.warranty_expiry, a.warranty_found) == ("2027-01-01", "2030-01-01")


async def test_editing_other_fields_keeps_the_dates_provenance(client, admin_headers, session_factory, admin_user):
    """The edit form re-sends every field. Moving an asset must not relabel an imported date
    'by hand' or drop a found date waiting for a choice."""
    a = await _asset(session_factory, admin_user.org_id, "Moved", warranty_expiry="2027-01-01",
                     warranty_source="csv", warranty_found="2028-01-01", warranty_found_source="csv")
    r = await client.patch(f"/api/v1/assets/{a}", headers=admin_headers,
                           json={"location": "Pune", "warranty_expiry": "2027-01-01"})
    assert (r.json()["warranty_source"], r.json()["warranty_found"]) == ("csv", "2028-01-01")
    bad = await client.patch(f"/api/v1/assets/{a}", headers=admin_headers, json={"warranty_expiry": "2026-12-99"})
    assert bad.status_code == 422
    day_first = await client.patch(f"/api/v1/assets/{a}", headers=admin_headers, json={"purchase_date": "05/04/2025"})
    assert day_first.json()["purchase_date"] == "2025-04-05"


async def test_csv_duplicates_bad_files_and_trails(client, admin_headers, session_factory, admin_user):
    org = admin_user.org_id
    a = await _asset(session_factory, org, "Dup", serial_number="D-1")
    manual = await _asset(session_factory, org, "Hand", serial_number="H-1", warranty_expiry="2026-01-01",
                          warranty_source="manual")
    body = (await _import(client, admin_headers,
                          "serial,warranty_expiry\nD-1,2027-01-01\nd-1,2029-01-01\nH-1,2027-02-02\n")).json()
    assert body["updated"] == 1 and any("more than once" in x for x in body["invalid"])
    assert (await _get(session_factory, a)).warranty_expiry == "2027-01-01"   # the first row, not the last
    huge = "serial,warranty_expiry\n\"" + "x" * 140_000 + "\",2027-01-01\n"
    assert (await _import(client, admin_headers, huge)).status_code == 400
    async with session_factory() as s:
        notes = [e.note for e in (await s.execute(select(AssetEvent).where(AssetEvent.asset_id == manual))).scalars()]
    assert any("kept 2026-01-01" in (n or "") for n in notes)   # a held conflict leaves a trace


def test_month_arithmetic():
    from app.services.warranty import warranty_from_invoice

    assert warranty_from_invoice({"invoice_date": "2026-01-31", "warranty_months": 1}) == "2026-02-28"
    assert warranty_from_invoice({"invoice_date": "31/12/2026", "warranty_months": 24}) == "2028-12-31"
    assert warranty_from_invoice({"warranty_end": "2027-05-05", "warranty_months": 99}) == "2027-05-05"
    assert warranty_from_invoice({"invoice_date": "2026-01-01", "warranty_months": 500}) is None


async def test_import_refusals(client, admin_headers, user_headers):
    assert (await _import(client, admin_headers, "name,date\nx,2027-01-01")).status_code == 400
    assert (await _import(client, user_headers, "serial,warranty_expiry\nA,2027-01-01")).status_code == 403
    assert (await client.post("/api/v1/assets/00000000-0000-0000-0000-000000000000/warranty/resolve",
                              headers=admin_headers, json={"keep": "found"})).status_code == 404
