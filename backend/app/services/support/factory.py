"""Building an organization's helpdesk connector, or deciding it has none.

Every reason this can return None is a reason the assistant must not offer to raise a
ticket: no settings row, disabled, half-configured, or a credential we can no longer
decrypt. Offering and then failing is worse than never offering — the user has already
been told help is coming.
"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.models import HelpdeskSettings
from app.services.support.connector import TicketConnector
from app.services.support.freshservice import FreshserviceConnector

logger = logging.getLogger(__name__)


async def get_settings_for(session: AsyncSession, org_id: uuid.UUID) -> HelpdeskSettings | None:
    result = await session.execute(
        select(HelpdeskSettings).where(HelpdeskSettings.org_id == org_id)
    )
    return result.scalars().first()


async def build_connector(
    session: AsyncSession, org_id: uuid.UUID
) -> TicketConnector | None:
    """The org's connector, or None when there is nothing usable to build one from."""
    settings = await get_settings_for(session, org_id)
    if settings is None or not settings.enabled:
        return None
    if not settings.domain or not settings.api_key_encrypted:
        # Saved but never finished. Treated as unconfigured rather than as an error,
        # because that is what it is.
        return None

    try:
        api_key = crypto.decrypt(settings.api_key_encrypted)
    except (crypto.CryptoUnavailable, crypto.DecryptionFailed) as exc:
        # Logged loudly: from the user's side this looks identical to "no helpdesk
        # connected", and an admin who set one up deserves to find out why it stopped.
        logger.error(
            "Helpdesk credential for org %s could not be decrypted: %s", org_id, exc
        )
        return None

    if settings.provider != "freshservice":
        logger.error("Unsupported helpdesk provider %r for org %s", settings.provider, org_id)
        return None

    return FreshserviceConnector(
        domain=settings.domain,
        api_key=api_key,
        default_priority=settings.default_priority,
        source=settings.default_source,
        workspace_id=settings.workspace_id,
        group_id=settings.group_id,
    )


def category_for(settings: HelpdeskSettings | None, action_id: str | None) -> tuple[
    str | None, str | None
]:
    """The org's category for the action ASTRA tried, if they mapped one.

    Unmapped returns (None, None) and the ticket is filed unclassified. That is
    deliberate: every helpdesk's category tree is its own, and a guessed category puts the
    ticket in front of the wrong team — which is worse than putting it in front of triage.
    """
    if settings is None or not settings.category_map or not action_id:
        return None, None
    entry = settings.category_map.get(action_id)
    if not isinstance(entry, dict):
        return None, None
    return entry.get("category"), entry.get("sub_category")
