"""Platform-operator (super-admin) API — manage ALL organizations. Every route
requires a platform admin."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_platform_admin
from app.core.database import get_db
from app.models import User
from app.models.invoice import InvoiceStatus
from app.models.organization import SubscriptionStatus
from app.models.support_request import SupportRequestStatus
from app.repositories.devices import DeviceRepository
from app.repositories.remediation import RemediationRepository
from app.repositories.telemetry import TelemetryRepository
from app.repositories.users import UserRepository
from app.schemas.asset import AssetRead
from app.schemas.billing_profile import BillingProfileRead, InvoiceRead
from app.schemas.devices import DeviceRead
from app.schemas.pagination import DEFAULT_PAGE_SIZE, Page, build
from app.schemas.help_centre import (
    HelpArticleAdminRead,
    HelpArticleCreate,
    HelpArticleUpdate,
)
from app.schemas.platform import (
    DiscountRequest,
    GlobalFixCreate,
    GlobalFixRead,
    OrganizationAdminRead,
    OrganizationCreate,
    OrganizationUpdate,
    PlatformAnalytics,
    PlatformAuditRead,
    PlatformBilling,
    PlatformOverview,
    PlatformReports,
    RemediationActionOption,
    ViewAsToken,
)
from app.schemas.remediation import RemediationTaskRead
from app.schemas.support_request import (
    SupportQueue,
    SupportReplyCreate,
    SupportRequestRead,
    SupportRequestSummary,
    SupportRequestUpdate,
)
from app.schemas.users import UserRead
from app.services.ai.knowledge import KnowledgeBaseService
from app.services.ai.learned import LearnedFixStore
from app.services.assets import AssetService
from app.services.billing_profile import BillingProfileService
from app.services.exceptions import NotFoundError
from app.services.platform import PlatformService
from app.services.support_requests import SupportRequestService
from app.services.remediation.actions import ACTIONS
from app.api.v1.support import thread_detail


def _fix_read(entry) -> GlobalFixRead:
    action = ACTIONS.get(entry.action_id)
    return GlobalFixRead(
        id=entry.id, problem=entry.query_text, action_id=entry.action_id,
        action_label=action.label if action else entry.action_id,
        params=entry.params, created_at=entry.created_at,
    )

router = APIRouter(prefix="/platform", tags=["platform"])


def _enrich_task(task, hostname_by_id: dict) -> RemediationTaskRead:
    read = RemediationTaskRead.model_validate(task)
    read.device_hostname = hostname_by_id.get(task.device_id)
    action = ACTIONS.get(task.action_id)
    read.action_label = action.label if action else task.action_id
    return read


@router.get(
    "/overview",
    response_model=PlatformOverview,
    summary="Aggregate stats across all organizations (platform admin)",
)
async def platform_overview(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> PlatformOverview:
    return await PlatformService(session).overview()


@router.get(
    "/billing",
    response_model=PlatformBilling,
    summary="Platform-wide revenue rollup: MRR/ARR, providers, per-org economics (platform admin)",
)
async def platform_billing(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> PlatformBilling:
    return await PlatformService(session).billing()


@router.get(
    "/analytics",
    response_model=PlatformAnalytics,
    summary="Revenue history and per-customer health scoring (platform admin)",
)
async def platform_analytics(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> PlatformAnalytics:
    """Invoice-backed revenue trend, conversion and churn ratios, and a health score per
    customer with the reasons behind it. Read-only, so nothing is audited here."""
    return await PlatformService(session).analytics()


@router.get(
    "/reports",
    response_model=PlatformReports,
    summary="Cross-org analytics: growth, self-healing outcomes, fleet, AI volume (platform admin)",
)
async def platform_reports(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> PlatformReports:
    return await PlatformService(session).reports()


@router.get(
    "/audit",
    response_model=list[PlatformAuditRead],
    summary="The operator's own action trail across all orgs (platform admin)",
)
async def platform_audit(
    limit: int = 100,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[PlatformAuditRead]:
    return await PlatformService(session).audit_feed(limit=min(max(limit, 1), 500))


@router.post(
    "/organizations/{org_id}/view-token",
    response_model=ViewAsToken,
    summary="Mint a read-only token to view an org's full portal (platform admin)",
)
async def create_view_token(
    org_id: uuid.UUID,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> ViewAsToken:
    return await PlatformService(session).create_view_as_token(actor=actor, org_id=org_id)


@router.post(
    "/organizations",
    response_model=OrganizationAdminRead,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a new organization + its first admin (platform admin)",
)
async def create_organization(
    body: OrganizationCreate,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> OrganizationAdminRead:
    return await PlatformService(session).create_organization(actor=actor, data=body)


@router.get(
    "/organizations",
    response_model=Page[OrganizationAdminRead],
    summary="Search + paginate organizations (platform admin)",
)
async def list_organizations(
    q: str | None = None,
    plan: str | None = None,
    subscription_status: SubscriptionStatus | None = None,
    country: str | None = None,
    sort: str = "created_at",
    desc: bool = True,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> Page[OrganizationAdminRead]:
    """Searched, filtered and sorted in the database.

    This used to return every organization with a per-org user and device count attached —
    fine at eleven, a full scan plus two aggregate queries at ten thousand, on a page that
    shows fifty rows.
    """
    items, total, page, page_size = await PlatformService(session).list_organizations_page(
        q=(q.strip() or None) if q else None,
        plan=plan, subscription_status=subscription_status,
        country=(country.strip().upper() or None) if country else None,
        sort=sort, desc=desc, page=page, page_size=page_size,
    )
    return build(items, total, page, page_size)


@router.get(
    "/invoices",
    response_model=Page[InvoiceRead],
    summary="Billing history across every organization (platform admin)",
)
async def platform_invoices(
    org_id: uuid.UUID | None = None,
    q: str | None = None,
    status_in: list[InvoiceStatus] | None = Query(default=None, alias="status"),
    issued_from: date | None = None,
    issued_to: date | None = None,
    sort: str = "issued_on",
    desc: bool = True,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> Page[InvoiceRead]:
    items, total, page, page_size = await BillingProfileService(session).list_invoices(
        org_id=org_id, q=q, status=status_in,
        issued_from=issued_from, issued_to=issued_to,
        sort=sort, desc=desc, page=page, page_size=page_size,
        # The operator's list has an organization column; resolved for the page only.
        with_org_names=True,
    )
    return build(items, total, page, page_size)


@router.get(
    "/organizations/{org_id}/billing-profile",
    response_model=BillingProfileRead,
    summary="An organization's billing and tax details (platform admin, read-only)",
)
async def platform_billing_profile(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> BillingProfileRead:
    """Read-only on purpose. The customer owns their own legal and tax identity; an operator
    editing it silently is how a wrong tax number ends up on an invoice with nobody able to
    say who typed it."""
    return await BillingProfileService(session).get_profile(org_id=org_id)


@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationAdminRead,
    summary="One organization's details (platform admin)",
)
async def get_organization(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> OrganizationAdminRead:
    return await PlatformService(session).get_organization(org_id)


@router.get(
    "/organizations/{org_id}/users",
    response_model=list[UserRead],
    summary="An organization's users (platform admin)",
)
async def organization_users(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[User]:
    return await UserRepository(session).list_by_org(org_id)


@router.get(
    "/organizations/{org_id}/devices",
    response_model=list[DeviceRead],
    summary="An organization's devices (platform admin)",
)
async def organization_devices(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceRead]:
    devices = await DeviceRepository(session).list_by_org(org_id)
    counts = await TelemetryRepository(session).count_apps_by_device_for_org(org_id)
    return [DeviceRead.from_device(d, counts.get(d.id, 0)) for d in devices]


@router.get(
    "/organizations/{org_id}/remediation",
    response_model=list[RemediationTaskRead],
    summary="An organization's self-healing history (platform admin)",
)
async def organization_remediation(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[RemediationTaskRead]:
    tasks = await RemediationRepository(session).list_by_org(org_id)
    devices = await DeviceRepository(session).list_by_org(org_id)
    hostname_by_id = {d.id: d.hostname for d in devices}
    return [_enrich_task(t, hostname_by_id) for t in tasks]


@router.get(
    "/organizations/{org_id}/assets",
    response_model=list[AssetRead],
    summary="An organization's assets (platform admin)",
)
async def organization_assets(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[AssetRead]:
    return await AssetService(session).list_for_org(org_id=org_id)


# ── Support requests: customers asking ASTRA itself for help ──────────────────
@router.get(
    "/support-requests",
    response_model=SupportQueue,
    summary="Support requests from every organization (platform admin)",
)
async def platform_support_queue(
    request_status: SupportRequestStatus | None = None,
    org_id: uuid.UUID | None = None,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> SupportQueue:
    """Ordered by whose turn it is, then priority, then how long it has waited — a thread
    parked on the customer is not something we owe anybody."""
    rows, counts, org_names = await SupportRequestService(session).queue(
        status=request_status, org_id=org_id
    )
    requests = []
    for r in rows:
        summary = SupportRequestSummary.model_validate(r)
        summary.org_name = org_names.get(str(r.org_id))
        requests.append(summary)
    return SupportQueue(requests=requests, counts_by_status=counts)


@router.get(
    "/support-requests/{request_id}",
    response_model=SupportRequestRead,
    summary="Read one support thread from any organization (platform admin)",
)
async def platform_support_thread(
    request_id: uuid.UUID,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> SupportRequestRead:
    return await thread_detail(
        SupportRequestService(session), actor=actor, request_id=request_id, operator=True
    )


@router.post(
    "/support-requests/{request_id}/replies",
    response_model=SupportRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="Answer a customer's support request (platform admin)",
)
async def platform_support_reply(
    request_id: uuid.UUID,
    body: SupportReplyCreate,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> SupportRequestRead:
    """Replying notifies the customer and hands the thread back to them."""
    service = SupportRequestService(session)
    await service.reply(
        actor=actor, request_id=request_id, body=body.body, from_operator=True
    )
    return await thread_detail(service, actor=actor, request_id=request_id, operator=True)


@router.patch(
    "/support-requests/{request_id}",
    response_model=SupportRequestSummary,
    summary="Set a support request's status or priority (platform admin)",
)
async def platform_support_update(
    request_id: uuid.UUID,
    body: SupportRequestUpdate,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> SupportRequestSummary:
    updated = await SupportRequestService(session).update(
        actor=actor, request_id=request_id,
        status=body.status, priority=body.priority,
    )
    return SupportRequestSummary.model_validate(updated)


# ── Global knowledge: problem→solution articles shared with EVERY organization ──
@router.get(
    "/knowledge",
    response_model=list[HelpArticleAdminRead],
    summary="List support articles, published and withdrawn (platform admin)",
)
async def list_global_knowledge(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[HelpArticleAdminRead]:
    """Every global article, published or not — this is the authoring view."""
    return [
        HelpArticleAdminRead.model_validate(a)
        for a in await KnowledgeBaseService(session).list_global()
    ]


@router.post(
    "/knowledge",
    response_model=HelpArticleAdminRead,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a support article to every organization (platform admin)",
)
async def create_global_knowledge(
    body: HelpArticleCreate,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> HelpArticleAdminRead:
    """Creates it published. An article written and left invisible helps nobody, and the
    operator can withdraw it in one call if it was not ready."""
    article = await KnowledgeBaseService(session).create_global(
        title=body.title, content=body.content, actor_user_id=actor.id,
        help_category=body.help_category, error_code=body.error_code,
    )
    return HelpArticleAdminRead.model_validate(article)


@router.patch(
    "/knowledge/{article_id}",
    response_model=HelpArticleAdminRead,
    summary="Edit, publish or withdraw a support article (platform admin)",
)
async def update_global_knowledge(
    article_id: uuid.UUID,
    body: HelpArticleUpdate,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> HelpArticleAdminRead:
    sent = body.model_fields_set
    article = await KnowledgeBaseService(session).update_global(
        article_id=article_id,
        title=body.title, content=body.content,
        help_category=body.help_category, error_code=body.error_code,
        published=body.published,
        # Sending the key as null means "remove this"; leaving it out means "don't touch".
        clear_category="help_category" in sent and body.help_category is None,
        clear_error_code="error_code" in sent and body.error_code is None,
    )
    return HelpArticleAdminRead.model_validate(article)


@router.delete(
    "/knowledge/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a global knowledge article (platform admin)",
)
async def delete_global_knowledge(
    article_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    await KnowledgeBaseService(session).delete_global(article_id=article_id)


# ── Global auto-apply fixes: problem → remediation action, applied for every org ──
@router.get(
    "/remediation-actions",
    response_model=list[RemediationActionOption],
    summary="Remediation actions available for a global fix (platform admin)",
)
async def list_remediation_actions(
    _: User = Depends(require_platform_admin),
) -> list[RemediationActionOption]:
    return [
        RemediationActionOption(id=a.id, label=a.label, tier=a.tier.value, params=list(a.params))
        for a in ACTIONS.values()
    ]


@router.get(
    "/fixes",
    response_model=list[GlobalFixRead],
    summary="List global auto-apply fixes (platform admin)",
)
async def list_global_fixes(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[GlobalFixRead]:
    return [_fix_read(e) for e in await LearnedFixStore(session).list_global()]


@router.post(
    "/fixes",
    response_model=GlobalFixRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a global auto-apply fix (platform admin)",
)
async def create_global_fix(
    body: GlobalFixCreate,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> GlobalFixRead:
    params: dict = {}
    if body.process_name:
        params["process_name"] = body.process_name
    if body.service_name:
        params["service_name"] = body.service_name
    try:
        entry = await LearnedFixStore(session).create_global(
            problem=body.problem, action_id=body.action_id, params=params or None
        )
    except ValueError as exc:
        raise NotFoundError(str(exc))
    return _fix_read(entry)


@router.delete(
    "/fixes/{fix_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a global auto-apply fix (platform admin)",
)
async def delete_global_fix(
    fix_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await LearnedFixStore(session).delete_global(fix_id=fix_id)
    except LookupError:
        raise NotFoundError("Global fix not found")


@router.patch(
    "/organizations/{org_id}",
    response_model=OrganizationAdminRead,
    summary="Update an organization's plan/status/trial (platform admin)",
)
async def update_organization(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> OrganizationAdminRead:
    return await PlatformService(session).update_organization(actor=actor, org_id=org_id, data=body)


@router.post(
    "/organizations/{org_id}/discount",
    response_model=OrganizationAdminRead,
    summary="Apply a percentage discount to an org (bulk pricing, platform admin)",
)
async def set_org_discount(
    org_id: uuid.UUID,
    body: DiscountRequest,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> OrganizationAdminRead:
    return await PlatformService(session).set_discount(actor=actor, org_id=org_id, percent=body.percent)


@router.delete(
    "/organizations/{org_id}/discount",
    response_model=OrganizationAdminRead,
    summary="Remove an org's discount (platform admin)",
)
async def clear_org_discount(
    org_id: uuid.UUID,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> OrganizationAdminRead:
    return await PlatformService(session).clear_discount(actor=actor, org_id=org_id)


@router.delete(
    "/organizations/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an organization and all its data (platform admin)",
)
async def delete_organization(
    org_id: uuid.UUID,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    await PlatformService(session).delete_organization(actor=actor, org_id=org_id)
