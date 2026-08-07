"""Freshservice adapter — https://api.freshservice.com/#create_ticket

Endpoint, auth and field shapes were read from the API reference; the required-field set
and the category tree came from a real instance's `ticket_form_fields`, not from memory.
That mattered: the worry going in was mandatory custom fields rejecting every create, and
in practice only five fields are required — requester, subject, description, status,
priority. Everything else the ticket needs (category, group, agent) is required for
*closure*, which is the technician's job, not ours.
"""
import base64
import logging
from typing import Any

import httpx

from app.services.support.connector import (
    TicketError,
    TicketRequest,
    TicketResult,
)

logger = logging.getLogger(__name__)

STATUS_OPEN = 2
PRIORITY = {"low": 1, "medium": 2, "high": 3, "urgent": 4}


class FreshserviceConnector:
    """Files tickets into one organization's Freshservice instance."""

    name = "freshservice"

    def __init__(
        self,
        *,
        domain: str,
        api_key: str,
        default_priority: int = 1,
        source: int | None = None,
        workspace_id: int | None = None,
        group_id: int | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.domain = domain.strip().removesuffix(".freshservice.com")
        self._api_key = api_key
        self.default_priority = default_priority
        self.source = source
        self.workspace_id = workspace_id
        self.group_id = group_id
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}.freshservice.com"

    def _auth_header(self) -> str:
        # Basic auth with the API key as the username and any password. "X" is the
        # convention in Freshservice's own examples.
        pair = base64.b64encode(f"{self._api_key}:X".encode()).decode()
        return f"Basic {pair}"

    def _payload(self, request: TicketRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "email": request.requester_email,
            "subject": request.subject,
            "description": request.description_html,
            "status": STATUS_OPEN,
            "priority": PRIORITY.get(request.priority.lower(), self.default_priority),
            # Tags rather than a custom source: a source has to be created by an admin
            # first, while a tag needs no setup and still lets their reporting answer
            # "how many tickets did ASTRA raise".
            "tags": request.tags,
        }
        if self.source is not None:
            payload["source"] = self.source
        if self.workspace_id is not None:
            payload["workspace_id"] = self.workspace_id
        if self.group_id is not None:
            payload["group_id"] = self.group_id
        # Only sent when the org configured a mapping. Category is not required at
        # creation, and guessing at someone else's category tree files tickets into the
        # wrong queue — worse than filing them unclassified.
        if request.category:
            payload["category"] = request.category
        if request.sub_category:
            payload["sub_category"] = request.sub_category
        return payload

    async def create_ticket(self, request: TicketRequest) -> TicketResult:
        if not request.requester_email:
            # Freshservice would create or guess a requester. A ticket attributed to the
            # wrong person breaks their SLA and CSAT reporting, and the employee never
            # hears back about their own problem.
            raise TicketError("No requester email — refusing to file an unattributed ticket")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v2/tickets",
                    headers={
                        "Authorization": self._auth_header(),
                        "Content-Type": "application/json",
                    },
                    json=self._payload(request),
                )
        except httpx.HTTPError as exc:
            raise TicketError(f"Could not reach Freshservice: {exc}") from exc

        if response.status_code == 201:
            return self._parse(response)

        raise TicketError(self._describe_failure(response))

    # -- Responses ----------------------------------------------------------

    @staticmethod
    def _parse(response: httpx.Response) -> TicketResult:
        try:
            ticket = (response.json() or {}).get("ticket") or {}
        except ValueError as exc:
            raise TicketError(f"Freshservice returned a 201 we could not read: {exc}") from exc

        ticket_id = ticket.get("id")
        if not ticket_id:
            # A 201 whose body has no id would otherwise be reported to the user as a
            # successfully raised ticket they can never be told the number of.
            raise TicketError("Freshservice accepted the ticket but returned no id")
        return TicketResult(external_id=str(ticket_id), url=None)

    def _describe_failure(self, response: httpx.Response) -> str:
        """Turn a rejection into something an operator can act on.

        These end up in `last_error` on the escalation and in the logs, and "400 Bad
        Request" alone has cost enough debugging hours to be worth the extra lines.
        """
        code = response.status_code
        hint = {
            401: "the API key was rejected",
            403: "the API key lacks permission to create tickets",
            404: f"no Freshservice instance at {self.domain}.freshservice.com",
            429: "Freshservice rate limit reached",
        }.get(code)

        detail = ""
        try:
            body = response.json() or {}
            errors = body.get("errors") or []
            if errors:
                # Freshservice names the offending field, which is the whole answer when
                # an org has made something mandatory that we are not sending.
                detail = "; ".join(
                    f"{e.get('field', '?')}: {e.get('message', e)}" for e in errors[:3]
                )
            elif body.get("description"):
                detail = str(body["description"])
        except ValueError:
            detail = response.text[:200]

        parts = [p for p in (hint, detail) if p]
        return f"Freshservice returned {code}" + (f" — {'; '.join(parts)}" if parts else "")


def ticket_url(domain: str, ticket_id: str) -> str:
    """Where a human goes to read the ticket. Built rather than read from the response:
    the create response carries the id, not an agent-facing link."""
    return f"https://{domain}.freshservice.com/a/tickets/{ticket_id}"
