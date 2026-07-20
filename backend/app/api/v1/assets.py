import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.asset import AssetCreate, AssetRead, AssetSummary, AssetUpdate
from app.schemas.asset_event import AssetPassport
from app.services.assets import AssetService

router = APIRouter(prefix="/assets", tags=["assets"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


def _ack_page(title: str, message: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>{title}</title></head>
        <body style="font-family:Segoe UI,Arial,sans-serif;background:#f8fafc;margin:0;
        display:flex;min-height:100vh;align-items:center;justify-content:center">
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:40px;
        max-width:420px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:#2563eb;margin-bottom:12px">⬡ ASTRA</div>
        <h1 style="font-size:18px;color:#0f172a;margin:0 0 8px">{title}</h1>
        <p style="color:#475569;margin:0">{message}</p></div></body></html>"""
    )


# Public — the opaque token in the emailed link is the proof, so no auth. Declared
# before "/{asset_id}" so the literal path wins.
@router.get(
    "/acknowledge",
    response_class=HTMLResponse,
    summary="Confirm receipt of an assigned asset (public, via emailed link)",
)
async def acknowledge_asset(
    token: str = "",
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    asset = await AssetService(session).acknowledge_by_token(token=token)
    if asset is None:
        return _ack_page(
            "Link not recognized",
            "This acknowledgement link is invalid or has expired. Please contact your IT team.",
        )
    return _ack_page(
        "Receipt confirmed",
        f"Thank you — your receipt of <strong>{asset.name}</strong> has been recorded.",
    )


@router.get("", response_model=list[AssetRead], summary="List assets in your organization")
async def list_assets(
    archived: bool = False,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[AssetRead]:
    return await AssetService(session).list_for_org(org_id=actor.org_id, archived=archived)


@router.get("/summary", response_model=AssetSummary, summary="Asset register summary")
async def asset_summary(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AssetSummary:
    return await AssetService(session).summary(org_id=actor.org_id)


@router.get("/{asset_id}", response_model=AssetRead, summary="Get an asset")
async def get_asset(
    asset_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    return await AssetService(session).get(actor=actor, asset_id=asset_id)


@router.get(
    "/{asset_id}/passport",
    response_model=AssetPassport,
    summary="Device passport — full lifecycle history + analytics",
)
async def asset_passport(
    asset_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AssetPassport:
    return await AssetService(session).passport(actor=actor, asset_id=asset_id)


@router.post(
    "", response_model=AssetRead, status_code=status.HTTP_201_CREATED,
    summary="Create an asset (staff)",
)
async def create_asset(
    body: AssetCreate,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    return await AssetService(session).create(actor=actor, data=body)


@router.patch("/{asset_id}", response_model=AssetRead, summary="Update an asset (staff)")
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    return await AssetService(session).update(actor=actor, asset_id=asset_id, data=body)


@router.post(
    "/{asset_id}/resend-acknowledgement",
    response_model=AssetRead,
    summary="Re-send the receipt-confirmation email to the assignee (staff)",
)
async def resend_acknowledgement(
    asset_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    return await AssetService(session).resend_acknowledgement(actor=actor, asset_id=asset_id)


@router.post(
    "/{asset_id}/archive", response_model=AssetRead,
    summary="Archive an asset — keeps its record + passport (staff)",
)
async def archive_asset(
    asset_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    return await AssetService(session).archive(actor=actor, asset_id=asset_id)


@router.post(
    "/{asset_id}/restore", response_model=AssetRead,
    summary="Restore an archived asset to the active register (staff)",
)
async def restore_asset(
    asset_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    return await AssetService(session).restore(actor=actor, asset_id=asset_id)


@router.delete(
    "/{asset_id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete an asset and its history (admin)",
)
async def delete_asset(
    asset_id: uuid.UUID,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> None:
    await AssetService(session).delete(actor=actor, asset_id=asset_id)
