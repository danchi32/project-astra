"""Phase 3b · I4 Client-Audit Pack: upload a client's questionnaire, get draft answers from
SAVIO's evidence with citations, review them, download the CSV. Admin only; an add-on."""
import base64
import binascii
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, requires
from app.core.database import get_db
from app.models import AuditPack, User, UserRole
from app.services import audit_pack
from app.services.audit import AuditService
from app.services.browser_policy import has_control
from app.services.entitlements import AUDIT_PACK

router = APIRouter(prefix="/audit-packs", tags=["audit-packs"], dependencies=[Depends(requires(AUDIT_PACK))])
admin = require_roles(UserRole.ADMIN)


class Evidence(BaseModel):
    key: str
    label: str
    link: str


class PackRow(BaseModel):
    n: int
    question: str
    status: Literal["pending", "answered", "gap"]
    answer: str | None = None
    evidence: list[Evidence] = []
    edited_by: str | None = None


class PackSummary(BaseModel):
    id: uuid.UUID
    name: str
    status: Literal["answering", "ready", "failed"]
    error: str | None
    created_at: datetime
    answered_at: datetime | None
    questions: int
    answered: int
    gaps: int


class PackRead(PackSummary):
    rows: list[PackRow]


class PackUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=5, max_length=200)          # the file's name: .xlsx or .csv
    content_base64: str = Field(min_length=4, max_length=2_900_000)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if has_control(v) or not v.lower().endswith((".xlsx", ".csv")):
            raise ValueError("an .xlsx or .csv file name")
        return v


class RowEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(max_length=audit_pack.MAX_ANSWER)
    status: Literal["answered", "gap"]

    @field_validator("answer")
    @classmethod
    def _answer(cls, v: str) -> str:
        if has_control(v.replace("\n", "")):
            raise ValueError("must be plain text")
        return v.strip()


@router.get("", response_model=list[PackSummary], summary="I4: the organization's questionnaires, newest first (admin)")
async def list_packs(actor: User = Depends(admin), session: AsyncSession = Depends(get_db)) -> list[PackSummary]:
    rows = (await session.execute(select(AuditPack).where(AuditPack.org_id == actor.org_id)
                                  .order_by(AuditPack.created_at.desc()))).scalars()
    return [PackSummary(**audit_pack.read(p)) for p in rows]


@router.post("", response_model=PackRead, status_code=status.HTTP_201_CREATED,
             summary="I4: upload a questionnaire (.xlsx / .csv, base64); SAVIO drafts answers in the background "
                     "(admin; audited)")
async def upload(
    body: PackUpload,
    background: BackgroundTasks,
    actor: User = Depends(admin),
    session: AsyncSession = Depends(get_db),
) -> PackRead:
    try:
        data = base64.b64decode(body.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "The file did not arrive intact") from exc
    # Off the event loop: reading a sheet is CPU work, and other requests must not wait on it.
    found = await run_in_threadpool(audit_pack.questions, body.name, data)
    if audit_pack._provider() is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The AI is not set up on this server")
    if await audit_pack.busy(session, actor.org_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Another questionnaire is still being answered")
    pack = AuditPack(org_id=actor.org_id, name=body.name, status="answering", created_by_user_id=actor.id,
                     rows=[{"n": i + 1, "question": q, "status": "pending", "answer": None, "evidence": []}
                           for i, q in enumerate(found)])
    session.add(pack)
    await session.flush()
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="audit_pack.create", target_type="audit_pack",
        target_id=str(pack.id), detail={"name": body.name, "questions": len(found)},
    )
    await session.commit()
    background.add_task(audit_pack.answer, pack.id, actor.org_id)
    return PackRead(**audit_pack.read(pack))


@router.get("/{pack_id}", response_model=PackRead, summary="I4: one questionnaire with its draft answers (admin)")
async def get_pack(pack_id: uuid.UUID, actor: User = Depends(admin), session: AsyncSession = Depends(get_db)) -> PackRead:
    return PackRead(**audit_pack.read(await audit_pack.get(session, actor.org_id, pack_id)))


@router.patch("/{pack_id}/rows/{n}", response_model=PackRead,
              summary="I4: a person's answer for one row, replacing the draft (admin; audited)")
async def edit_row(
    pack_id: uuid.UUID, n: int, body: RowEdit,
    actor: User = Depends(admin), session: AsyncSession = Depends(get_db),
) -> PackRead:
    pack = await audit_pack.get(session, actor.org_id, pack_id)
    if pack.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Wait until SAVIO has finished drafting")
    rows = [dict(r) for r in pack.rows]
    row = next((r for r in rows if r["n"] == n), None)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such question")
    row.update(answer=body.answer, status=body.status, edited_by=actor.full_name)
    pack.rows = rows
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="audit_pack.row_edit", target_type="audit_pack",
        target_id=str(pack.id), detail={"n": n, "status": body.status},
    )
    await session.commit()
    return PackRead(**audit_pack.read(pack))


@router.get("/{pack_id}/export", summary="I4: the answers as CSV, for the client (admin; audited)",
            response_class=Response)
async def export(pack_id: uuid.UUID, actor: User = Depends(admin), session: AsyncSession = Depends(get_db)) -> Response:
    pack = await audit_pack.get(session, actor.org_id, pack_id)
    if pack.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Wait until SAVIO has finished drafting")
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="audit_pack.export", target_type="audit_pack",
        target_id=str(pack.id), detail={"name": pack.name},
    )
    await session.commit()
    stem = pack.name.rsplit(".", 1)[0]
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in stem)[:80] or "questionnaire"
    return Response(content="﻿" + audit_pack.to_csv(pack), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{safe} - SAVIO answers.csv"'})


@router.delete("/{pack_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="I4: delete a questionnaire and its answers (admin; audited)")
async def delete_pack(pack_id: uuid.UUID, actor: User = Depends(admin), session: AsyncSession = Depends(get_db)) -> None:
    pack = await audit_pack.get(session, actor.org_id, pack_id)
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="audit_pack.delete", target_type="audit_pack",
        target_id=str(pack.id), detail={"name": pack.name},
    )
    await session.delete(pack)
    await session.commit()
