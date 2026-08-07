"""The evidence that travels with an escalated ticket.

An ordinary helpdesk ticket says "my laptop is slow". A technician then spends the first
twenty minutes finding out what "slow" means, what the machine is doing, and what has
already been tried.

ASTRA already knows all three. It watched the telemetry, it attempted fixes, it recorded
what each one changed. Attaching that turns the ticket from a question into a report, and
it is the one thing a helpdesk cannot produce for itself — the ticket is not the
differentiator, the dossier is.

Written as HTML because every helpdesk renders a ticket description as HTML, and a wall of
plain text is exactly what gets skimmed past.
"""
import html
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Attempt:
    """One thing ASTRA tried, and what actually changed. `outcome` is the agent's own
    measurement where it reported one ("Freed 2.1 GB") — the difference between a claim
    and a result."""

    label: str
    succeeded: bool
    outcome: str | None = None
    at: datetime | None = None


@dataclass
class Dossier:
    problem: str                       # the user's own words, verbatim
    hostname: str | None = None
    os_version: str | None = None
    reported_at: datetime | None = None
    facts: list[tuple[str, str]] = field(default_factory=list)   # telemetry worth reading
    attempts: list[Attempt] = field(default_factory=list)
    knowledge_hit: str | None = None   # matching runbook title, if retrieval found one
    device_url: str | None = None      # deep link back into ASTRA

    def subject(self) -> str:
        """What a technician scanning a queue sees. The user's words first, because that is
        what they will match against when the person phones to chase it."""
        words = " ".join(self.problem.split())[:80]
        where = f" — {self.hostname}" if self.hostname else ""
        return f"[ASTRA] {words}{where}"

    def to_html(self) -> str:
        e = html.escape
        parts = [
            "<p><strong>Reported by the user:</strong><br>",
            f"&ldquo;{e(self.problem)}&rdquo;",
        ]
        if self.reported_at:
            parts.append(f"<br><em>{self.reported_at:%Y-%m-%d %H:%M UTC}</em>")
        parts.append("</p>")

        if self.hostname or self.os_version or self.facts:
            parts.append("<p><strong>Device</strong><br>")
            bits = [b for b in (e(self.hostname or ""), e(self.os_version or "")) if b]
            if bits:
                parts.append(" &middot; ".join(bits) + "<br>")
            parts.extend(f"{e(k)}: {e(v)}<br>" for k, v in self.facts)
            parts.append("</p>")

        parts.append("<p><strong>What ASTRA already tried</strong><br>")
        if self.attempts:
            for a in self.attempts:
                mark = "&#10003;" if a.succeeded else "&#10007;"
                when = f"{a.at:%H:%M} " if a.at else ""
                tail = f" &mdash; {e(a.outcome)}" if a.outcome else ""
                parts.append(f"{when}{mark} {e(a.label)}{tail}<br>")
        else:
            # Said explicitly rather than left blank: "no automatic fix applies to this"
            # is itself a finding, and it tells the technician not to look for one.
            parts.append("No automatic fix applies to this problem.<br>")
        parts.append("</p>")

        parts.append("<p><strong>Knowledge base</strong><br>")
        parts.append(
            f"Matching article: {e(self.knowledge_hit)}<br>" if self.knowledge_hit
            else "No matching runbook.<br>"
        )
        parts.append("</p>")

        if self.device_url:
            # The hook: a technician who follows this is reading ASTRA without anyone
            # having bought it for them.
            parts.append(
                f'<p><a href="{e(self.device_url)}">Full device timeline in ASTRA</a></p>'
            )
        parts.append(
            "<p><em>Raised automatically by ASTRA after the user agreed to escalate.</em></p>"
        )
        return "".join(parts)
