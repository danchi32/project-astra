from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import EmailSendMethod, EmailSettings, User, UserRole
from app.schemas.email_settings import (
    AssetEmailTemplateUpdate,
    AssetPlaceholder,
    AssetPlaceholderGroup,
    EmailDnsRecord,
    EmailSenderChoice,
    EmailSettingsConfigure,
    EmailSettingsRead,
)
from app.models import EmailVerificationStatus
from app.services.email_templates import (
    ASSET_PLACEHOLDERS,
    DEFAULT_ASSET_BODY,
    DEFAULT_ASSET_SUBJECT,
    placeholder_groups,
)
from app.schemas.settings import (
    OrganizationSettingsRead,
    OrganizationSettingsUpdate,
    PermissionMatrix,
)
from app.services.email_domains import EmailProviderError, provider_configured
from app.services.email_integration import EmailIntegrationService, SharedSenderNotEntitled
from app.services.settings import SettingsService
from app.schemas.helpdesk import (
    HelpdeskSettingsRead,
    HelpdeskSettingsUpdate,
    HelpdeskVerifyResult,
)
from app.services.support.settings import HelpdeskConfigError, HelpdeskSettingsService

router = APIRouter(prefix="/settings", tags=["settings"])

admin_required = require_roles(UserRole.ADMIN)


def _effective_from(row: EmailSettings | None, org_name: str) -> str:
    """The From line a recipient will see, worked out the same way the send path does.

    Shown rather than described, because "we will send on your behalf" leaves an admin
    guessing what lands in their employee's inbox — and the answer is the whole difference
    between the two options.
    """
    from app.core.config import get_settings as _s

    if (
        row is not None
        and row.method is EmailSendMethod.DNS
        and row.status is EmailVerificationStatus.VERIFIED
        and row.from_address
    ):
        return f"{row.from_name or org_name} <{row.from_address}>"
    shared = _s().email_from or "(no platform sender configured)"
    return f"{(row.from_name if row else None) or org_name} (via ASTRA) <{shared}>"


async def _email_read_for(
    session: AsyncSession, actor: User, row: EmailSettings | None
) -> EmailSettingsRead:
    """The read model with everything that needs a database lookup already resolved —
    the org's name for the From preview, and whether the shared sender is on their plan."""
    read = _email_read(row, await _org_name(session, actor))
    read.shared_sender_available = await EmailIntegrationService.shared_sender_allowed(
        session, actor.org_id
    )
    return read


async def _org_name(session: AsyncSession, actor: User) -> str:
    """The organization's own name, so the From preview shows what the admin will actually
    see rather than the placeholder "Your organization"."""
    from app.models import Organization

    org = await session.get(Organization, actor.org_id)
    return org.name if org else "Your organization"


def _placeholder_groups() -> list[AssetPlaceholderGroup]:
    return [
        AssetPlaceholderGroup(
            key=key,
            title=title,
            placeholders=[
                AssetPlaceholder(
                    key=s.key, label=s.label, sample=s.sample, needs_device=s.needs_device,
                )
                for s in specs
            ],
        )
        for key, title, specs in placeholder_groups()
    ]


def _email_read(row: EmailSettings | None, org_name: str = "Your organization") -> EmailSettingsRead:
    ready = provider_configured()
    if row is None:
        return EmailSettingsRead(
            configured=False, provider_ready=ready,
            status=EmailVerificationStatus.UNCONFIGURED,
            method=EmailSendMethod.SHARED,
            effective_from=_effective_from(None, org_name),
            asset_email_subject=DEFAULT_ASSET_SUBJECT,
            asset_email_body=DEFAULT_ASSET_BODY,
            asset_email_placeholders=ASSET_PLACEHOLDERS,
            asset_email_placeholder_groups=_placeholder_groups(),
        )
    return EmailSettingsRead(
        configured=bool(row.from_address),
        provider_ready=ready,
        status=row.status,
        method=row.method,
        effective_from=_effective_from(row, org_name),
        reply_to=row.reply_to,
        from_name=row.from_name,
        from_address=row.from_address,
        domain=row.domain,
        dns_records=[EmailDnsRecord(**r) for r in (row.dns_records or [])],
        last_error=row.last_error,
        verified_at=row.verified_at,
        # Show the org's template, falling back to the shipped default so the editor is populated.
        asset_email_subject=row.asset_email_subject or DEFAULT_ASSET_SUBJECT,
        asset_email_body=row.asset_email_body or DEFAULT_ASSET_BODY,
        # The shipped default is plain text, so a row that has no body of its own is showing
        # plain text whatever format its own (absent) body was saved in.
        asset_email_body_format=(row.asset_email_body_format if row.asset_email_body else "text"),
        asset_email_placeholders=ASSET_PLACEHOLDERS,
        asset_email_placeholder_groups=_placeholder_groups(),
        asset_email_cc=row.asset_email_cc or [],
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
    return await _email_read_for(session, actor, row)


@router.put(
    "/email/sender",
    response_model=EmailSettingsRead,
    summary="Choose how mail is sent: ASTRA's shared address, or your own domain (admin)",
)
async def choose_email_sender(
    body: EmailSenderChoice,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> EmailSettingsRead:
    try:
        row = await EmailIntegrationService(session).choose_sender(
            actor=actor, method=body.method,
            from_name=body.from_name,
            reply_to=str(body.reply_to) if body.reply_to else None,
        )
    except SharedSenderNotEntitled as exc:
        # 402, not 403 — the caller has the right role, their plan simply does not include
        # this. "Ask your administrator" and "upgrade your plan" are different next steps.
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc),
            headers={"X-Astra-Required-Feature": "shared_email_sender"},
        )
    return await _email_read_for(session, actor, row)


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
    return await _email_read_for(session, actor, row)


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
    return await _email_read_for(session, actor, row)


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
        actor=actor, subject=body.subject, body=body.body, cc=body.cc,
        body_format=body.body_format,
    )
    return await _email_read_for(session, actor, row)


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
    "/helpdesk",
    response_model=HelpdeskSettingsRead,
    summary="Get the helpdesk connection (admin)",
)
async def get_helpdesk_settings(
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> HelpdeskSettingsRead:
    return await HelpdeskSettingsService(session).get(org_id=actor.org_id)


@router.patch(
    "/helpdesk",
    response_model=HelpdeskSettingsRead,
    summary="Update the helpdesk connection (admin)",
)
async def update_helpdesk_settings(
    body: HelpdeskSettingsUpdate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> HelpdeskSettingsRead:
    try:
        return await HelpdeskSettingsService(session).update(actor=actor, payload=body)
    except HelpdeskConfigError as exc:
        # A deployment problem, not the administrator's mistake — 503 rather than 400, so
        # they are not left rereading a form that is filled in correctly.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.post(
    "/helpdesk/verify",
    response_model=HelpdeskVerifyResult,
    summary="Check the helpdesk connection works (admin)",
)
async def verify_helpdesk_settings(
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> HelpdeskVerifyResult:
    """Reads the instance's field schema. Creates nothing — an administrator can press
    this as often as they like without leaving test tickets in their own queue."""
    ok, detail = await HelpdeskSettingsService(session).verify(actor=actor)
    return HelpdeskVerifyResult(ok=ok, detail=detail)


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
