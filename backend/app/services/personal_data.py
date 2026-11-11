"""Z2 — everything SAVIO holds about one person: export it, or erase it.

Our customer (the organisation) is the Data Fiduciary for its staff; we are its processor.
When an employee asks the organisation for their data, or to be forgotten, an admin answers
from here instead of filing a ticket with us.

A "person" is two identities that SAVIO does not link on its own:

* their **portal user** (account, chats, assets, support escalations, audit entries), and
* the **Windows usernames** they sign in to computers with (Tracker attendance and app use,
  signed-in sessions, apps installed into their profile).

Tracker records `DOMAIN\\user` per device and nothing maps that to a portal user, so the admin
confirms which Windows usernames are this person; `candidates()` suggests the likely ones.

Erase removes what is *about* the person and keeps what is a *security record* — but the
record stops pointing at them:

* deleted: the user, their chats, sessions/tokens, team memberships, escalations, and every
  Tracker / session / per-user-app row for the confirmed Windows usernames;
* unlinked: assets they held (asset stays, unassigned), asset history, support tickets;
* pseudonymised: audit entries keep their row and the action, but the person's email, name
  and Windows usernames inside them become `erased-user-<id>`; action records (remediations,
  remote sessions, deployments) keep only the user's ID, which leads nowhere once the user
  row is gone.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

from sqlalchemy import String, cast, delete, func, inspect, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivitySample,
    Asset,
    AssetEvent,
    AuditLog,
    Conversation,
    DailyAppUsage,
    DailyUserSummary,
    Deployment,
    DeviceInstalledApp,
    DeviceLocalAccount,
    DeviceSession,
    Message,
    PasswordResetToken,
    RefreshToken,
    RemediationTask,
    RemoteSession,
    SupportEscalation,
    SupportRequest,
    SupportRequestMessage,
    User,
    UserTeamMember,
    WorkSession,
)
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError

#: Never exported: secrets and machine-only columns that say nothing about the person.
_SKIP = {"hashed_password", "token_hash", "embedding", "embedding_model", "org_id"}
#: Tracker tables keyed by Windows username — deleted on erase.
_BY_USERNAME = (ActivitySample, WorkSession, DailyUserSummary, DailyAppUsage, DeviceSession)


def pseudonym(user_id: uuid.UUID) -> str:
    return f"erased-user-{hashlib.sha256(str(user_id).encode()).hexdigest()[:8]}"


def _row(obj: Any) -> dict:
    return {a.key: getattr(obj, a.key) for a in inspect(obj).mapper.column_attrs if a.key not in _SKIP}


def _clean(names: list[str]) -> list[str]:
    return sorted({n.strip() for n in names if n and n.strip()})


def _username_match(col, names: list[str]):
    """`asha` matches `asha` and `ACME\\asha`; `ACME\\asha` matches only itself. Case-insensitive,
    as Windows is."""
    if not names:
        return None
    conds = []
    for n in names:
        conds.append(func.lower(col) == n.lower())
        if "\\" not in n:
            # endswith + autoescape, not LIKE '%\\name': Postgres reads that backslash as an
            # escape, so the pattern would become '%name' and match "ACME\\ganasha" too.
            conds.append(func.lower(col).endswith("\\" + n.lower(), autoescape=True))
    return or_(*conds)


class PersonalDataService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _user(self, actor: User, user_id: uuid.UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None or user.org_id != actor.org_id:
            raise NotFoundError("User not found")
        return user

    async def candidates(self, actor: User, user_id: uuid.UUID) -> list[str]:
        """Windows usernames seen in this org that look like this person (email local part, or
        a part of their name of 3+ letters)."""
        user = await self._user(actor, user_id)
        hints = {user.email.split("@")[0].lower()} | {
            p.lower() for p in user.full_name.replace(".", " ").split() if len(p) >= 3}
        seen: set[str] = set()
        for model in (DailyUserSummary, DeviceSession):
            seen |= {u for (u,) in (await self.session.execute(
                select(model.username).where(model.org_id == actor.org_id, model.username.is_not(None))
                .distinct())).all()}
        return sorted(u for u in seen if any(h in u.lower().split("\\")[-1] for h in hints))

    async def _selects(self, user: User, names: list[str]) -> dict[str, Any]:
        org, uid = user.org_id, user.id
        q: dict[str, Any] = {
            "conversations": select(Conversation).where(Conversation.org_id == org, Conversation.user_id == uid),
            "team_memberships": select(UserTeamMember).where(UserTeamMember.user_id == uid),
            "assets_assigned": select(Asset).where(Asset.org_id == org, Asset.assigned_to_user_id == uid),
            "asset_history": select(AssetEvent).where(AssetEvent.org_id == org, AssetEvent.user_id == uid),
            "support_escalations": select(SupportEscalation).where(
                SupportEscalation.org_id == org, SupportEscalation.user_id == uid),
            "support_requests": select(SupportRequest).where(
                SupportRequest.org_id == org, SupportRequest.created_by_user_id == uid),
            "remediations": select(RemediationTask).where(RemediationTask.org_id == org, or_(
                RemediationTask.requested_by_user_id == uid, RemediationTask.approved_by_user_id == uid)),
            "remote_sessions": select(RemoteSession).where(
                RemoteSession.org_id == org, RemoteSession.requested_by_user_id == uid),
            "deployments": select(Deployment).where(Deployment.org_id == org, Deployment.created_by_user_id == uid),
            "audit_entries": select(AuditLog).where(AuditLog.org_id == org, self._audit_about(user, names)),
        }
        for model in _BY_USERNAME:
            q[model.__tablename__] = select(model).where(
                model.org_id == org, _username_match(model.username, names)) if names else None
        q["apps_in_their_profile"] = select(DeviceInstalledApp).where(
            DeviceInstalledApp.org_id == org, DeviceInstalledApp.scope == "user",
            _username_match(DeviceInstalledApp.user_name, names)) if names else None
        q["windows_accounts"] = select(DeviceLocalAccount).where(
            DeviceLocalAccount.org_id == org, _username_match(DeviceLocalAccount.name, names)) if names else None
        return q

    @staticmethod
    def _audit_about(user: User, names: list[str]):
        # A wide net on purpose; _replace() then changes only whole-token matches. Usernames
        # are searched by their part after the backslash: in the detail's JSON text the
        # backslash itself is escaped ("ACME\\\\asha"), so the full form never matches.
        # autoescape: Postgres LIKE treats "\\" (and "_", "%") as special; SQLite does not.
        # NOT the full name: any user can set their own name (PATCH /auth/me), so "e" or another
        # admin's email as a name would pull — and on erase rewrite — the whole org's audit log.
        # Email is set by an admin and Windows usernames are confirmed by one.
        text = cast(AuditLog.detail, String)
        needles = {user.email, *(n.split("\\")[-1] for n in names)}
        return or_(
            AuditLog.actor_id == user.id,
            (AuditLog.target_type == "user") & (AuditLog.target_id == str(user.id)),
            *(text.contains(n, autoescape=True) for n in needles if n),
        )

    @staticmethod
    def _tied_by_id(entry: AuditLog, user: User) -> bool:
        return entry.actor_id == user.id or (entry.target_type == "user" and entry.target_id == str(user.id))

    async def summary(self, actor: User, user_id: uuid.UUID, names: list[str]) -> dict:
        """The dry run: how many rows each erase step would touch. Nothing changes."""
        user = await self._user(actor, user_id)
        names = _clean(names)
        counts = {}
        for key, stmt in (await self._selects(user, names)).items():
            counts[key] = 0 if stmt is None else await self.session.scalar(
                select(func.count()).select_from(stmt.subquery()))
        return {
            "user": {"id": str(user.id), "email": user.email, "full_name": user.full_name},
            "windows_usernames": names,
            "counts": counts,
            "erase": {
                "deleted": ["account", "conversations", "team_memberships", "support_escalations",
                            *[m.__tablename__ for m in _BY_USERNAME], "apps_in_their_profile"],
                "unlinked": ["assets_assigned", "asset_history", "support_requests"],
                "pseudonymised": ["audit_entries", "remediations", "remote_sessions", "deployments"],
                "kept": ["windows_accounts"],
            },
            "pseudonym": pseudonym(user.id),
        }

    async def export(self, actor: User, user_id: uuid.UUID, names: list[str]) -> dict:
        user = await self._user(actor, user_id)
        names = _clean(names)
        out: dict[str, Any] = {"account": _row(user), "windows_usernames": names}
        for key, stmt in (await self._selects(user, names)).items():
            rows = [] if stmt is None else list((await self.session.execute(stmt)).scalars().all())
            out[key] = [_row(r) for r in rows]
            if key == "remediations":
                # A technician's export would otherwise carry other accounts' one-time
                # passwords (in `result`) and other people's details (in `params`).
                for data in out[key]:
                    data.pop("result", None)
                    data.pop("params", None)
            if key == "conversations":
                for conv, data in zip(rows, out[key]):
                    data["messages"] = [_row(m) for m in (await self.session.execute(
                        select(Message).where(Message.conversation_id == conv.id)
                        .order_by(Message.created_at))).scalars().all()]
            if key == "support_requests":
                for req, data in zip(rows, out[key]):
                    data["messages"] = [_row(m) for m in (await self.session.execute(
                        select(SupportRequestMessage).where(SupportRequestMessage.request_id == req.id,
                                                            SupportRequestMessage.author_user_id == user.id)
                    )).scalars().all()]
        await AuditService(self.session).record(
            org_id=actor.org_id, actor_id=actor.id, action="user.personal_data_export",
            target_type="user", target_id=str(user.id),
            detail={"windows_usernames": len(names), "sections": {k: len(v) for k, v in out.items()
                                                                   if isinstance(v, list)}})
        await self.session.commit()
        return out

    async def erase(self, actor: User, user_id: uuid.UUID, names: list[str], confirm_email: str) -> dict:
        user = await self._user(actor, user_id)
        if user.id == actor.id:
            raise ConflictError("You cannot erase your own account — ask another admin")
        if user.is_platform_admin:
            raise ConflictError("A platform operator account can't be erased from here")
        if confirm_email.strip().lower() != user.email.lower():
            raise ConflictError("Type the person's email exactly to confirm the erase")
        names = _clean(names)
        before = (await self.summary(actor, user_id, names))["counts"]
        return await self._erase(actor, user, names, action="user.personal_data_erase",
                                 detail={"windows_usernames": len(names), "counts": before})

    async def delete_account(self, actor: User, user: User) -> str:
        """The Users page's plain "Delete": the account-side half of an erase, with no Windows
        usernames, so the audit trail stops naming the person too (Record of Processing, G10)."""
        return (await self._erase(actor, user, [], action="user.delete", detail={}))["person"]

    async def _erase(self, actor: User, user: User, names: list[str], *, action: str, detail: dict) -> dict:
        before = detail.get("counts")
        alias = pseudonym(user.id)
        org, uid = user.org_id, user.id

        # Pseudonymise audit entries before anything else: the match uses the email.
        # The full name is replaced only inside entries tied to this user by id, where it can only
        # mean them; elsewhere a self-chosen name could rewrite other people's history.
        # Longest first: "Asha Verma" before the bare username "asha", or the name half-survives.
        for entry in (await self.session.execute(
                select(AuditLog).where(AuditLog.org_id == org, self._audit_about(user, names)))).scalars():
            if entry.detail:
                own = self._tied_by_id(entry, user) and len(user.full_name.strip()) >= 3
                needles = [user.email, *([user.full_name] if own else []), *names]
                entry.detail = _replace(entry.detail, needles, alias)

        for model in _BY_USERNAME if names else ():
            await self.session.execute(delete(model).where(
                model.org_id == org, _username_match(model.username, names)))
        if names:
            await self.session.execute(delete(DeviceInstalledApp).where(
                DeviceInstalledApp.org_id == org, DeviceInstalledApp.scope == "user",
                _username_match(DeviceInstalledApp.user_name, names)))

        conv_ids = select(Conversation.id).where(Conversation.org_id == org, Conversation.user_id == uid)
        await self.session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
        await self.session.execute(delete(Conversation).where(Conversation.org_id == org, Conversation.user_id == uid))
        await self.session.execute(delete(SupportEscalation).where(
            SupportEscalation.org_id == org, SupportEscalation.user_id == uid))
        for model in (UserTeamMember, RefreshToken, PasswordResetToken):
            await self.session.execute(delete(model).where(model.user_id == uid))

        await self.session.execute(update(Asset).where(Asset.org_id == org, Asset.assigned_to_user_id == uid)
                                   .values(assigned_to_user_id=None))
        await self.session.execute(update(AssetEvent).where(AssetEvent.org_id == org, AssetEvent.user_id == uid)
                                   .values(user_id=None))
        for col in (AssetEvent.from_value, AssetEvent.to_value):
            await self.session.execute(update(AssetEvent).where(
                AssetEvent.org_id == org, col.in_([user.full_name, user.email])).values({col: alias}))
        await self.session.execute(update(SupportRequest).where(
            SupportRequest.org_id == org, SupportRequest.created_by_user_id == uid).values(created_by_user_id=None))
        await self.session.execute(update(SupportRequestMessage).where(
            SupportRequestMessage.author_user_id == uid).values(author_user_id=None))
        await self.session.execute(update(Deployment).where(
            Deployment.org_id == org, Deployment.created_by_user_id == uid).values(created_by_user_id=None))

        await self.session.delete(user)
        # The erase's own audit entry names the pseudonym, never the person.
        await AuditService(self.session).record(
            org_id=actor.org_id, actor_id=actor.id, action=action,
            target_type="user", target_id=str(uid), detail={"person": alias, **detail})
        await self.session.commit()
        return {"person": alias, "counts": before}


def _replace(value: Any, needles: list[str], alias: str) -> Any:
    """Whole-token replace, so erasing "Asha" leaves "Ashadeep" alone; case-insensitive.
    `ACME\asha` becomes `ACME\\erased-user-…` — the domain says nothing about the person."""
    if isinstance(value, str):
        for n in needles:
            if n:
                value = re.sub(rf"(?<![\w.@-]){re.escape(n)}(?![\w.@-])", alias, value, flags=re.IGNORECASE)
        return value
    if isinstance(value, dict):
        return {k: _replace(v, needles, alias) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace(v, needles, alias) for v in value]
    return value
