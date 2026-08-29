"""Check marketing copy against what ASTRA can actually do.

This exists before any generator does, and that ordering is the point. A checker without a
generator is still useful — it can be run over the website that already exists, which is
how the "device certificates" claim was found. A generator without a checker is a machine
that states falsehoods confidently.

Two layers, the same split the lead scorer uses and for the same reason:

* **Rules** are patterns from `brand/claims.yaml`. Deterministic, no network, no key. They
  produce BLOCKERS, and a blocker means the copy does not reach a human for approval — it
  goes back. The patterns live in the YAML rather than here so that the file a person
  reviews and the file the machine enforces are one file.
* **The model pass** reads the whole claim file and the whole draft, and catches what
  patterns cannot: a sentence that implies a capability without using any forbidden word.
  It only ever produces WARNINGS. It cannot clear a blocker, and it cannot create one.

That asymmetry is deliberate. A regex can be trusted to stop something; a model cannot be
trusted to permit it.
"""
import functools
import logging
import pathlib
import re
from dataclasses import dataclass, field
from typing import Literal

import yaml

from app.core.config import get_settings

logger = logging.getLogger("astra.mkt.claims")
settings = get_settings()

CLAIMS_PATH = pathlib.Path(__file__).resolve().parents[2] / "brand" / "claims.yaml"

Severity = Literal["blocker", "warning"]

#: How much text to show either side of a match. Enough to judge it without reprinting
#: the whole draft in an alert.
_CONTEXT_CHARS = 60


@dataclass(frozen=True)
class Finding:
    severity: Severity
    rule: str
    matched: str
    context: str
    guidance: str

    def __str__(self) -> str:
        mark = "BLOCK" if self.severity == "blocker" else "warn "
        return f"[{mark}] {self.rule}: {self.matched!r} — {self.guidance}"


@dataclass
class CheckResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def blockers(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "blocker"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def passed(self) -> bool:
        """Whether this copy may be shown to a human for approval.

        Warnings do not stop it — they travel with it, so the approver sees what to look
        at. Blockers do: there is no version of "the product does not do this" that a
        reviewer should be asked to weigh up under time pressure.
        """
        return not self.blockers


@functools.lru_cache(maxsize=1)
def load_claims() -> dict:
    """Parse claims.yaml once per process.

    Cached because it is read on every generation and never changes at runtime — it is a
    file in the image, edited by humans and shipped by a deploy.
    """
    return yaml.safe_load(CLAIMS_PATH.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def _compiled_rules() -> tuple[list[tuple[re.Pattern, str, str, Severity]], ...]:
    """Every pattern, compiled once, paired with its rule id and guidance."""
    claims = load_claims()
    rules: list[tuple[re.Pattern, str, str, Severity]] = []

    for entry in claims.get("forbidden", []):
        guidance = entry.get("reality", "")
        # `match` blocks: the phrasing attaches the capability to ASTRA.
        for pattern in entry.get("match", []):
            rules.append((re.compile(pattern), entry["id"], guidance, "blocker"))
        # `warn_match` asks a person. The word appeared, but only a reader can tell whose
        # column it was in — the comparison pages name macOS and Linux honestly, in the
        # competitor's column, and a first pass blocked all four of them.
        for pattern in entry.get("warn_match", []):
            rules.append((re.compile(pattern), entry["id"], guidance, "warning"))

    for group in claims.get("unproven", {}).get("patterns", []):
        for pattern in group["match"]:
            rules.append((re.compile(pattern), group["id"], group.get("why", ""), "warning"))

    return (rules,)


def _context(text: str, start: int, end: int) -> str:
    left = max(0, start - _CONTEXT_CHARS)
    right = min(len(text), end + _CONTEXT_CHARS)
    snippet = text[left:right].replace("\n", " ").strip()
    return f"{'…' if left else ''}{snippet}{'…' if right < len(text) else ''}"


def check_text(text: str) -> CheckResult:
    """Run the deterministic pass. Never raises, never calls out.

    Cheap enough to run on every draft and on every revision, which matters: a checker
    people skip because it is slow protects nothing.
    """
    result = CheckResult()
    if not text:
        return result

    seen: set[tuple[str, str]] = set()
    for pattern, rule, guidance, severity in _compiled_rules()[0]:
        for match in pattern.finditer(text):
            key = (rule, match.group(0).lower())
            if key in seen:
                # One finding per rule per distinct phrase. Repeating "macOS" twelve times
                # in a long article is one problem, not twelve.
                continue
            seen.add(key)
            result.findings.append(Finding(
                severity=severity,
                rule=rule,
                matched=match.group(0),
                context=_context(text, match.start(), match.end()),
                guidance=guidance,
            ))
    return result


def claimable_actions() -> dict[str, list[str]]:
    """The action catalogue, by tier — for prompting a generator with what is true."""
    actions = load_claims()["actions"]
    return {tier: list(actions[tier]) for tier in
            ("automatic", "approval_required", "admin_only")}


def brand_bible_prompt() -> str:
    """The claim file rendered for a system prompt.

    Sent as a stable prefix so it sits inside the cached portion of every generation
    request — the file is a few thousand tokens and is identical on every call, which is
    exactly the shape prompt caching is for.
    """
    claims = load_claims()
    lines = [
        "ASTRA is a governed AI system administrator for Windows endpoint fleets.",
        "",
        "WHAT IT DOES — do not claim anything outside this list:",
    ]
    for capability in claims["capabilities"]:
        lines.append(f"  - {' '.join(capability['claim'].split())}")

    lines += ["", "REMEDIATION ACTIONS, by approval tier:"]
    for tier, ids in claimable_actions().items():
        lines.append(f"  {tier}: {', '.join(ids)}")
    withheld = claims["actions"]["withheld_from_ai"]
    lines += [
        f"  Never describe ASTRA as choosing to do these; a human asks: {', '.join(withheld)}",
        "",
        "NEVER CLAIM — each of these is false:",
    ]
    for entry in claims["forbidden"]:
        lines.append(f"  - {entry['never_claim']} Reality: {' '.join(entry['reality'].split())}")

    lines += ["", "TRUE BUT UNPROVEN — no customer has backed these, so do not state them:"]
    for rule in claims["unproven"]["rules"]:
        lines.append(f"  - {rule}")

    lines += [
        "",
        "If a sentence needs a number to work, the sentence is wrong. Describe the "
        "mechanism instead: what ASTRA gathers, what it proposes, who approves it, and "
        "what it records.",
    ]
    return "\n".join(lines)
