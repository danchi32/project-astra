"""Phase 3b · I1: the breach workflow — a record of a possible personal-data breach and the steps
taken, each with when and by whom, printable as an incident report (J7).

The steps are a working list, not the law: whether, to whom and by when anything must be reported
is for the organisation's counsel, so "Ask your counsel" is a step and reporting steps can be
marked "not needed" on that advice. The clock shows time since the breach was found and nothing
more. Every change is audited, and the audit entries are the record's timeline.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, GuardCase, GuardIncident, User
from app.models.base import utcnow
from app.services.audit import AuditService

TARGET = "guard_incident"
# (key, title, what it means). Order is the order they are usually done in.
STEPS = (
    ("contain", "Stop it going further",
     "Block the site, the account or the USB drive; take the PC off the network if needed."),
    ("assess", "Work out what and whose",
     "Which data, whose, about how many people, and whether it could be misused."),
    ("counsel", "Ask your counsel",
     "What has to be reported, to whom and by when depends on the facts: your counsel decides."),
    ("board", "Report to the Data Protection Board, if counsel says so",
     "Record when it was reported and the reference, or that counsel said it was not needed."),
    ("people", "Tell the people affected, if counsel says so",
     "Record how and when they were told, or that counsel said it was not needed."),
    ("fix", "Fix what let it happen",
     "Change the policy, the access or the training so it does not happen again."),
)
STEP_KEYS = tuple(k for k, _, _ in STEPS)
# Only reporting can be "not needed", and only on counsel's advice; the rest must be done.
OPTIONAL = ("board", "people")


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "No such breach record")


async def get(session: AsyncSession, org_id, incident_id: uuid.UUID) -> GuardIncident:
    row = await session.get(GuardIncident, incident_id)
    if row is None or row.org_id != org_id:
        raise _not_found()
    return row


def read(row: GuardIncident) -> dict:
    return {
        "id": row.id, "case_id": row.case_id, "title": row.title, "what_happened": row.what_happened,
        "found_at": row.found_at, "kinds": row.kinds, "people_affected": row.people_affected,
        "status": row.status, "opened_at": row.opened_at, "closed_at": row.closed_at,
        "steps": [{"key": k, "title": t, "help": h, "optional": k in OPTIONAL, **(row.steps.get(k) or {})}
                  for k, t, h in STEPS],
    }


async def list_for(session: AsyncSession, org_id) -> list[dict]:
    rows = (await session.execute(select(GuardIncident).where(GuardIncident.org_id == org_id)
                                  .order_by(GuardIncident.status.desc(), GuardIncident.found_at.desc()))).scalars()
    return [read(r) for r in rows]   # "open" > "closed": open records first


async def detail(session: AsyncSession, row: GuardIncident) -> dict:
    """The record, its case in brief, and its timeline from the audit log."""
    case = await session.get(GuardCase, row.case_id) if row.case_id else None
    entries = (await session.execute(
        select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.actor_id)
        .where(AuditLog.org_id == row.org_id, AuditLog.target_type == TARGET, AuditLog.target_id == str(row.id))
        .order_by(AuditLog.created_at))).all()
    return {
        **read(row),
        "case": {"id": case.id, "windows_user": case.windows_user, "opened_at": case.opened_at,
                 "level": case.level, "summary": case.summary} if case else None,
        "timeline": [{"at": a.created_at, "by": name, "action": a.action, "detail": a.detail} for a, name in entries],
    }


async def open_(session: AsyncSession, *, actor: User, title: str, what_happened: str, found_at: datetime,
                kinds: list[str], people_affected: int | None, case_id: uuid.UUID | None) -> GuardIncident:
    if case_id is not None:
        case = await session.get(GuardCase, case_id)
        if case is None or case.org_id != actor.org_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such case")
    row = GuardIncident(org_id=actor.org_id, case_id=case_id, title=title, what_happened=what_happened,
                        found_at=found_at, kinds=kinds, people_affected=people_affected, status="open", steps={},
                        opened_by_user_id=actor.id, opened_at=utcnow())
    session.add(row)
    await session.flush()
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="dpdp.incident_open", target_type=TARGET,
        # No title or text: technicians read the audit log, and a breach record is for admins (3b M2).
        target_id=str(row.id), detail={"found_at": found_at.isoformat(), "case_id": str(case_id) if case_id else None},
    )
    await session.commit()
    return row


async def update(session: AsyncSession, *, actor: User, row: GuardIncident, fields: dict,
                 step: dict | None, close: bool | None) -> GuardIncident:
    """Edit the facts, set one step, or close / reopen. Closing needs every step settled."""
    # The audit says what changed, never the words: technicians read the audit log, and the
    # record itself is for admins (security review 3b M2).
    changed: dict = {}
    for name, value in fields.items():
        if getattr(row, name) != value:
            setattr(row, name, value)
            changed.setdefault("fields", []).append(name)
    if step is not None:
        key, state = step["key"], step["state"]
        if state == "not_needed" and key not in OPTIONAL:
            raise HTTPException(422, "Only reporting steps can be marked not needed")
        steps = dict(row.steps)
        if state is None:
            steps.pop(key, None)
        else:
            steps[key] = {"state": state, "at": utcnow().isoformat(), "by": actor.full_name, "note": step.get("note")}
        row.steps = steps
        changed["step"] = {"key": key, "state": state}
    if close is not None and close != (row.status == "closed"):
        if close and any(k not in row.steps for k in STEP_KEYS):
            raise HTTPException(status.HTTP_409_CONFLICT, "Settle every step before closing the record")
        row.status, row.closed_at = ("closed", utcnow()) if close else ("open", None)
        changed["status"] = row.status
    if changed:
        await AuditService(session).record(
            org_id=actor.org_id, actor_id=actor.id, action="dpdp.incident_update", target_type=TARGET,
            target_id=str(row.id), detail=changed,
        )
        await session.commit()
    return row
