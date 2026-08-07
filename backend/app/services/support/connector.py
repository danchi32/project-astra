"""The seam between ASTRA and whatever helpdesk the customer already runs.

The pitch this whole feature answers is "why would we pay for two ticketing systems" — so
ASTRA does not become one. It hands a well-evidenced ticket to the system the customer
already trusts and stops there. That makes the port small: create a ticket, report where it
landed.

Everything above this line is vendor-independent — the escalation record, the consent gate,
deduplication, the dossier. Only auth, field names and status vocabulary differ per vendor,
and those live in the adapters.
"""
from dataclasses import dataclass, field
from typing import Protocol


class TicketError(RuntimeError):
    """The helpdesk refused the ticket or could not be reached.

    Raised, never swallowed into a success. The assistant's next sentence is either "I've
    raised ticket #123" or "I couldn't reach your helpdesk" — and it must be the true one.
    A user told a ticket exists when it doesn't waits for a reply that will never come.
    """


@dataclass
class TicketRequest:
    """What every helpdesk needs, in ASTRA's vocabulary rather than any vendor's."""

    requester_email: str
    subject: str
    description_html: str
    # ASTRA does not decide how urgent a customer's problems are — this is the org's
    # configured default, not a guess from the symptom.
    priority: str = "low"
    # Best-effort routing hints. Dropped by an adapter whose helpdesk has no equivalent
    # rather than being forced into some nearest match.
    category: str | None = None
    sub_category: str | None = None
    tags: list[str] = field(default_factory=lambda: ["astra"])


@dataclass
class TicketResult:
    external_id: str
    url: str | None = None


class TicketConnector(Protocol):
    """One helpdesk. `name` is stored on the escalation so a ticket can be traced back to
    the system it was filed in, which matters once an org changes helpdesk."""

    name: str

    async def create_ticket(self, request: TicketRequest) -> TicketResult: ...


class MockConnector:
    """Records what it was asked to file. Used by tests, and by a local run with no
    helpdesk configured — so the whole escalation path can be exercised end to end without
    creating a ticket in anybody's real queue."""

    name = "mock"

    def __init__(self, *, fail_with: str | None = None) -> None:
        self.requests: list[TicketRequest] = []
        self._fail_with = fail_with
        self._counter = 0

    async def create_ticket(self, request: TicketRequest) -> TicketResult:
        if self._fail_with:
            raise TicketError(self._fail_with)
        self.requests.append(request)
        self._counter += 1
        return TicketResult(
            external_id=str(1000 + self._counter),
            url=f"https://mock.helpdesk.local/tickets/{1000 + self._counter}",
        )
