"""L5b · Warranty: where an asset's warranty date came from, and never losing a person's value.

Every way a warranty date arrives goes through `apply_found`: CSV import today, the vendor
connectors (Dell, HP, Lenovo) and invoice reading later. The rule is the roadmap's: **a lookup
never silently overwrites a value a person entered.** If they differ, the found date is held
beside it and the admin picks one.

A date counts as a person's when `warranty_source` is "manual", or when there is a date with
no source at all (entered before sources were recorded, so by a person).

ponytail: no vendor connector yet. Each needs approved API access (Dell TechDirect, HP
developer portal, Lenovo), and writing a client against an API we cannot call yet would be
guesswork. When access arrives, a connector returns {serial: date} and calls
`apply_found(asset, date, "dell_api")`. Nothing else here changes.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, AssetEvent, AssetEventType, User
from app.models.base import utcnow
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError, ValidationError

SOURCES = ("manual", "csv", "invoice_ai", "dell_api", "hp_api", "lenovo_api")
MAX_CSV_BYTES = 1_000_000
MAX_CSV_ROWS = 5000
_SOURCE_WORDS = {"csv": "CSV import", "invoice_ai": "invoice", "dell_api": "Dell",
                 "hp_api": "HP", "lenovo_api": "Lenovo", "manual": "entered by hand"}


def parse_date(raw: str) -> str:
    """ISO (2027-03-31), or day first as Indian invoices write it (31-03-2027, 31/03/2027)."""
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"'{raw}' is not a date (use YYYY-MM-DD or DD/MM/YYYY)")


def is_persons(asset: Asset) -> bool:
    return asset.warranty_expiry is not None and asset.warranty_source in (None, "manual")


# Sources that only fill a blank, never replace an existing date of any kind. A model reading
# third-party text can be steered, so its date never overwrites even one a person imported.
_FILL_ONLY = ("invoice_ai",)


def apply_found(asset: Asset, found: str, source: str) -> tuple[str, str | None]:
    """Record a warranty date from `source`.

    Returns ("set" | "same" | "conflict", the passport note or None). A conflict is noted
    too, so a found date that is later dropped has left a trace.
    """
    if source not in SOURCES or source == "manual":
        raise ValueError(source)
    asset.warranty_checked_at = utcnow()
    words = _SOURCE_WORDS[source]
    if asset.warranty_expiry == found:
        dropped = asset.warranty_found
        asset.warranty_found = asset.warranty_found_source = None
        return "same", (f"Warranty {found} confirmed by {words}; the other date {dropped} no longer applies"
                        if dropped else None)
    if is_persons(asset) or (source in _FILL_ONLY and asset.warranty_expiry):
        asset.warranty_found, asset.warranty_found_source = found, source
        return "conflict", f"{words} says warranty {found}; kept {asset.warranty_expiry} until someone chooses"
    previous = asset.warranty_expiry
    asset.warranty_expiry, asset.warranty_source = found, source
    asset.warranty_found = asset.warranty_found_source = None
    return "set", f"Warranty {previous or 'unset'} → {found} (from {words})"


def _event(session: AsyncSession, asset: Asset, actor_id, note: str) -> None:
    session.add(AssetEvent(org_id=asset.org_id, asset_id=asset.id, event_type=AssetEventType.NOTE,
                           actor_id=actor_id, note=note[:500], occurred_at=utcnow()))


async def import_csv(session: AsyncSession, *, actor: User, text: str) -> dict:
    """Rows of serial_number or asset_tag + warranty_expiry. Matched within the org only."""
    if len(text.encode("utf-8")) > MAX_CSV_BYTES:
        raise ValidationError("The file is over 1 MB.")
    try:
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
        headers = {(h or "").strip().lower(): h for h in (reader.fieldnames or [])}
        rows = list(reader)                     # all parsed (and counted) before any query
    except csv.Error as exc:
        raise ValidationError(f"That file is not a readable CSV ({exc}).") from exc
    if len(rows) > MAX_CSV_ROWS:
        raise ValidationError(f"At most {MAX_CSV_ROWS} rows per file.")
    serial_h = headers.get("serial_number") or headers.get("serial")
    tag_h = headers.get("asset_tag")
    date_h = headers.get("warranty_expiry") or headers.get("warranty_end")
    if not date_h or not (serial_h or tag_h):
        raise ValidationError("The CSV needs a warranty_expiry column and a serial_number or asset_tag column.")

    out = {"rows": len(rows), "updated": 0, "unchanged": 0, "conflicts": 0, "unmatched": [], "invalid": []}
    seen: set[str] = set()
    for line, row in enumerate(rows, start=2):
        serial = str(row.get(serial_h) or "").strip()[:150] if serial_h else ""
        tag = str(row.get(tag_h) or "").strip()[:60] if tag_h else ""
        if not serial and not tag:
            out["invalid"].append(f"line {line}: no serial number or asset tag")
            continue
        key = f"s:{serial.lower()}" if serial else f"t:{tag.lower()}"
        if key in seen:
            # The same asset twice in one file: which date is right? Refuse rather than let
            # whichever row comes last win.
            out["invalid"].append(f"line {line}: '{serial or tag}' appears more than once in the file")
            continue
        seen.add(key)
        try:
            found = parse_date(str(row.get(date_h) or "")[:20])
        except ValueError as exc:
            out["invalid"].append(f"line {line}: {exc}")
            continue
        match = [Asset.serial_number.is_not(None) & (func.lower(Asset.serial_number) == serial.lower())] if serial else []
        match += [Asset.asset_tag.is_not(None) & (func.lower(Asset.asset_tag) == tag.lower())] if tag else []
        assets = (await session.execute(select(Asset).where(
            Asset.org_id == actor.org_id, Asset.archived_at.is_(None), or_(*match)))).scalars().all()
        if not assets:
            out["unmatched"].append(serial or tag)
            continue
        if len(assets) > 1:
            out["invalid"].append(f"line {line}: '{serial or tag}' matches {len(assets)} assets")
            continue
        asset = assets[0]
        result, note = apply_found(asset, found, "csv")
        if note:
            _event(session, asset, actor.id, note)
        out[{"set": "updated", "same": "unchanged", "conflict": "conflicts"}[result]] += 1
    out["unmatched"] = [u[:60] for u in out["unmatched"]]

    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="asset.warranty_import",
        target_type="organization", target_id=str(actor.org_id),
        detail={k: (len(v) if isinstance(v, list) else v) for k, v in out.items()},
    )
    await session.commit()
    out["unmatched"], out["invalid"] = out["unmatched"][:20], out["invalid"][:20]
    return out


def _add_months(day: str, months: int) -> str:
    d = datetime.strptime(day, "%Y-%m-%d").date()
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    for last in (31, 30, 29, 28):          # 31 Jan + 1 month -> 28/29 Feb, not an error
        try:
            return d.replace(year=year, month=month, day=min(d.day, last)).isoformat()
        except ValueError:
            continue
    raise ValueError(day)


def warranty_from_invoice(fields: dict) -> str | None:
    """The end date the invoice states, else its date plus the months it states, else None."""
    if fields.get("warranty_end"):
        return parse_date(str(fields["warranty_end"]))
    if fields.get("invoice_date") and isinstance(fields.get("warranty_months"), int) and 0 < fields["warranty_months"] <= 120:
        return _add_months(parse_date(str(fields["invoice_date"])), fields["warranty_months"])
    return None


MAX_INVOICES_PER_USER_HOUR = 20
MAX_INVOICES_PER_ORG_DAY = 100


async def apply_invoice(session: AsyncSession, *, actor: User, asset_id: uuid.UUID,
                        data_b64: str, media_type: str) -> dict:
    """Read an invoice for one asset and record what it says: warranty through `apply_found`;
    purchase date and cost only where the asset has none.

    Each read is a paid model call, so it is limited (per person per hour, per org per day)
    and recorded before it is made, whether it then succeeds or not. The database connection
    is released while the model reads: a slow call must not hold one of a handful of pooled
    connections that every tenant's requests share.
    """
    from datetime import timedelta

    from sqlalchemy import func as sqlfunc

    from app.models import AuditLog
    from app.services.invoice_reader import read_invoice

    org_id, actor_id = actor.org_id, actor.id
    asset = await session.get(Asset, asset_id)
    if asset is None or asset.org_id != org_id:
        raise NotFoundError("Asset not found")
    now = utcnow()

    async def count(since, **who):
        return await session.scalar(select(sqlfunc.count()).select_from(AuditLog).where(
            AuditLog.org_id == org_id, AuditLog.action == "asset.warranty_invoice_read",
            AuditLog.created_at >= since, *[getattr(AuditLog, k) == v for k, v in who.items()]))

    if await count(now - timedelta(hours=1), actor_id=actor_id) >= MAX_INVOICES_PER_USER_HOUR:
        raise ConflictError(f"At most {MAX_INVOICES_PER_USER_HOUR} invoices an hour per person. Try again later.")
    if await count(now - timedelta(days=1)) >= MAX_INVOICES_PER_ORG_DAY:
        raise ConflictError(f"Your organization has read {MAX_INVOICES_PER_ORG_DAY} invoices today. Try again tomorrow.")
    # Recorded and committed before the call: a call that then fails still cost money and
    # still counts, and the commit releases the connection for the length of the model call.
    await AuditService(session).record(
        org_id=org_id, actor_id=actor_id, action="asset.warranty_invoice_read",
        target_type="asset", target_id=str(asset_id), detail={"media_type": media_type},
    )
    await session.commit()

    fields = await read_invoice(data_b64=data_b64, media_type=media_type)

    asset = await session.get(Asset, asset_id, populate_existing=True)
    if asset is None or asset.org_id != org_id:
        raise NotFoundError("Asset not found")
    # The wrong invoice on the right asset is the likely mistake: if the invoice lists serials
    # and this asset has one, it must be among them.
    serials = {x.strip().lower() for x in fields.serial_numbers if x.strip()}
    if serials and asset.serial_number and asset.serial_number.strip().lower() not in serials:
        raise ValidationError(f"This invoice lists serial number(s) {', '.join(sorted(serials))[:200]}, "
                              f"not this asset's ({asset.serial_number}).")
    try:
        found = warranty_from_invoice(fields.model_dump())
    except ValueError:
        found = None
    result, note = apply_found(asset, found, "invoice_ai") if found else ("not_stated", None)
    if note:
        _event(session, asset, actor_id, note)
    filled = []
    try:
        bought = parse_date(fields.invoice_date) if fields.invoice_date else None
    except ValueError:
        bought = None
    if bought and not asset.purchase_date:
        asset.purchase_date = bought
        filled.append("purchase date")
    if fields.total_cost and asset.purchase_cost is None:
        asset.purchase_cost = fields.total_cost
        filled.append("purchase cost")
    if filled:
        _event(session, asset, actor_id, f"Filled from an invoice: {', '.join(filled)}")
    await AuditService(session).record(
        org_id=org_id, actor_id=actor_id, action="asset.warranty_invoice",
        target_type="asset", target_id=str(asset.id),
        # The fields read, never the file.
        detail={"result": result, "warranty": found, "filled": filled, "vendor": fields.vendor},
    )
    await session.commit()
    return {"result": result, "warranty_found": found, "filled": filled, "vendor": fields.vendor,
            "invoice_date": bought}


async def resolve(session: AsyncSession, *, actor: User, asset_id: uuid.UUID, keep: str) -> Asset:
    """The admin picks: keep the date a person entered, or take the one that was found."""
    asset = await session.get(Asset, asset_id)
    if asset is None or asset.org_id != actor.org_id:
        raise NotFoundError("Asset not found")
    if asset.warranty_found is None:
        raise ConflictError("There is no other warranty date to choose between.")
    found, source, previous = asset.warranty_found, asset.warranty_found_source, asset.warranty_expiry
    if keep == "found":
        asset.warranty_expiry, asset.warranty_source = found, source
    asset.warranty_found = asset.warranty_found_source = None
    note = (f"Warranty {previous} → {found} (chose the {_SOURCE_WORDS.get(source, source)} date)"
            if keep == "found" else
            f"Kept warranty {previous}; ignored {found} from {_SOURCE_WORDS.get(source, source)}")
    _event(session, asset, actor.id, note)
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="asset.warranty_resolve",
        target_type="asset", target_id=str(asset.id),
        detail={"kept": keep, "current": previous, "found": found, "source": source},
    )
    await session.commit()
    return asset
