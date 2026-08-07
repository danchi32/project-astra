"""Reading and writing an organization's helpdesk connection.

Three rules, all about the credential:

  It is write-only. It goes in through PATCH and never comes back out — the portal gets a
  mask, which answers "which key is saved" without answering "what is it".

  It is never stored in the clear. With no encryption key configured, saving is refused
  rather than falling back — a plaintext secret nobody knows is plaintext is worse than a
  feature that visibly will not turn on.

  Every change is audited, and the audit entry records that a credential changed, never
  the credential.
"""
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.models import HelpdeskSettings, User
from app.models.base import utcnow
from app.schemas.helpdesk import HelpdeskSettingsRead, HelpdeskSettingsUpdate
from app.services.audit import AuditService
from app.services.exceptions import ServiceError
from app.services.support import factory
from app.services.support.connector import TicketError

logger = logging.getLogger(__name__)


class HelpdeskConfigError(ServiceError):
    pass


class HelpdeskSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def _row(self, org_id: uuid.UUID) -> HelpdeskSettings:
        settings = await factory.get_settings_for(self.session, org_id)
        if settings is None:
            settings = HelpdeskSettings(org_id=org_id)
            self.session.add(settings)
            await self.session.flush()
        return settings

    async def get(self, *, org_id: uuid.UUID) -> HelpdeskSettingsRead:
        settings = await self._row(org_id)
        return self._read(settings)

    async def update(
        self, *, actor: User, payload: HelpdeskSettingsUpdate
    ) -> HelpdeskSettingsRead:
        settings = await self._row(actor.org_id)
        changed = payload.model_dump(exclude_unset=True)
        api_key = changed.pop("api_key", None)

        for field, value in changed.items():
            setattr(settings, field, value)

        if api_key:
            if not crypto.is_available():
                raise HelpdeskConfigError(
                    "Credential storage is not configured on this deployment "
                    "(ASTRA_SECRETS_KEY). The helpdesk API key cannot be saved."
                )
            settings.api_key_encrypted = crypto.encrypt(api_key)
            # A new credential invalidates whatever the last verification proved.
            settings.last_verified_at = None
            settings.last_error = None

        if changed.get("enabled") is False:
            settings.last_error = None

        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="helpdesk.settings.update",
            target_type="helpdesk_settings",
            target_id=str(settings.id),
            # Field names only. What changed is the useful record; the value of a
            # credential never belongs in an audit log.
            detail={"fields": sorted(changed.keys()) + (["api_key"] if api_key else [])},
        )
        await self.session.commit()
        return self._read(settings)

    async def verify(self, *, actor: User) -> tuple[bool, str | None]:
        """Prove the saved connection works, creating nothing.

        Runs the connector's read-only check so an administrator finds out about a wrong
        subdomain or a revoked key here, rather than when a user has already been told a
        ticket is on its way.
        """
        settings = await self._row(actor.org_id)
        connector = await factory.build_connector(self.session, actor.org_id)
        if connector is None:
            detail = self._why_not_ready(settings)
            settings.last_error = detail
            await self.session.commit()
            return False, detail

        try:
            await connector.verify()
        except TicketError as exc:
            settings.last_error = str(exc)[:500]
            settings.last_verified_at = None
            await self.session.commit()
            return False, str(exc)

        settings.last_error = None
        settings.last_verified_at = utcnow()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="helpdesk.settings.verify",
            target_type="helpdesk_settings", target_id=str(settings.id),
            detail={"provider": settings.provider, "domain": settings.domain},
        )
        await self.session.commit()
        return True, None

    # -- Presentation -------------------------------------------------------

    @staticmethod
    def _why_not_ready(settings: HelpdeskSettings) -> str:
        """Say which piece is missing. "Not configured" sends an admin back to a form they
        have already filled in most of."""
        if not settings.enabled:
            return "The helpdesk connection is turned off."
        if not settings.domain:
            return "No Freshservice domain has been set."
        if not settings.api_key_encrypted:
            return "No API key has been saved."
        if not crypto.is_available():
            return "Credential storage is not configured on this deployment."
        return "The saved credential could not be decrypted — please re-enter the API key."

    def _read(self, settings: HelpdeskSettings) -> HelpdeskSettingsRead:
        masked = ""
        if settings.api_key_encrypted:
            try:
                masked = crypto.mask(crypto.decrypt(settings.api_key_encrypted))
            except (crypto.CryptoUnavailable, crypto.DecryptionFailed):
                # Shown rather than hidden: an admin looking at a saved-but-unusable key
                # needs to know it must be re-entered.
                masked = "unreadable"

        return HelpdeskSettingsRead(
            provider=settings.provider,
            enabled=settings.enabled,
            domain=settings.domain,
            api_key_masked=masked,
            default_priority=settings.default_priority,
            default_source=settings.default_source,
            workspace_id=settings.workspace_id,
            group_id=settings.group_id,
            category_map=settings.category_map,
            last_error=settings.last_error,
            last_verified_at=settings.last_verified_at,
            ready=bool(
                settings.enabled and settings.domain and settings.api_key_encrypted
                and masked not in ("", "unreadable")
            ),
        )
