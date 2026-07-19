from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import EmailSettings, User, UserRole
from app.schemas.email_settings import (
    AssetEmailTemplateUpdate,
    EmailDnsRecord,
    EmailSettingsConfigure,
    EmailSettingsRead,
)
from app.models import EmailVerificationStatus
from app.services.email_templates import (
    ASSET_PLACEHOLDERS,
    DEFAULT_ASSET_BODY,
    DEFAULT_ASSET_SUBJECT,
)
from app.schemas.settings import (
    OrganizationSettingsRead,
    OrganizationSettingsUpdate,
    PermissionMatrix,
)
from app.services.email_domains import EmailProviderError, provider_configured
from app.services.email_integration import EmailIntegrationService
from app.services.settings import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])

admin_required = require_roles(UserRole.ADMIN)


def _email_read(row: EmailSettings | None) -> EmailSettingsRead:
    ready = provider_configured()
    if row is None:
        return EmailSettingsRead(
            configured=False, provider_ready=ready,
            status=EmailVerificationStatus.UNCONFIGURED,
            asset_email_subject=DEFAULT_ASSET_SUBJECT,
            asset_email_body=DEFAULT_ASSET_BODY,
            asset_email_placeholders=ASSET_PLACEHOLDERS,
        )
    return EmailSettingsRead(
        configured=bool(row.from_address),
        provider_ready=ready,
        status=row.status,
        from_name=row.from_name,
        from_address=row.from_address,
        domain=row.domain,
        dns_records=[EmailDnsRecord(**r) for r in (row.dns_records or [])],
        last_error=row.last_error,
        verified_at=row.verified_at,
        # Show the org's template, falling back to the shipped default so the editor is populated.
        asset_email_subject=row.asset_email_subject or DEFAULT_ASSET_SUBJECT,
        asset_email_body=row.asset_email_body or DEFAULT_ASSET_BODY,
        asset_email_placeholders=ASSET_PLACEHOLDERS,
    )


@router.get(
    "/email",
    response_model=EmailSettingsRead,
    summary="Get the org's outbound-email (sending domain) settings (admin)",
)
async def get_email_settings(
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> EmailSettingsRead:
    row = await EmailIntegrationService(session).read(org_id=actor.org_id)
    return _email_read(row)


@router.post(
    "/email",
    response_model=EmailSettingsRead,
    summary="Set the sending address and register the domain (admin)",
)
async def configure_email_settings(
    body: EmailSettingsConfigure,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> EmailSettingsRead:
    try:
        row = await EmailIntegrationService(session).configure(
            actor=actor, from_name=body.from_name, from_address=str(body.from_address)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except EmailProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return _email_read(row)


@router.post(
    "/email/verify",
    response_model=EmailSettingsRead,
    summary="Re-check the DNS records and update verification status (admin)",
)
async def verify_email_settings(
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> EmailSettingsRead:
    try:
        row = await EmailIntegrationService(session).verify(actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except EmailProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return _email_read(row)


@router.put(
    "/email/asset-template",
    response_model=EmailSettingsRead,
    summary="Customize the asset-assignment email template (admin)",
)
async def update_asset_email_template(
    body: AssetEmailTemplateUpdate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> EmailSettingsRead:
    row = await EmailIntegrationService(session).update_asset_template(
        actor=actor, subject=body.subject, body=body.body
    )
    return _email_read(row)


@router.get(
    "/organization",
    response_model=OrganizationSettingsRead,
    summary="Get organization settings (admin)",
)
async def get_org_settings(
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> OrganizationSettingsRead:
    return await SettingsService(session).read(actor=actor)


@router.patch(
    "/organization",
    response_model=OrganizationSettingsRead,
    summary="Update organization settings (admin)",
)
async def update_org_settings(
    body: OrganizationSettingsUpdate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> OrganizationSettingsRead:
    return await SettingsService(session).update(actor=actor, data=body)


@router.get(
    "/permissions",
    response_model=PermissionMatrix,
    summary="Role capability matrix for this organization",
)
async def get_permission_matrix(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PermissionMatrix:
    return await SettingsService(session).permission_matrix(org_id=actor.org_id)
