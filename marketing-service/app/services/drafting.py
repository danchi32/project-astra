"""Write marketing copy against the Brand Bible.

Two things shape this module.

**The Brand Bible is the system prompt, and it is cached.** It is a few thousand tokens,
byte-identical on every call, and sent ahead of anything that varies — which is the exact
shape prompt caching exists for. Cache reads are a tenth of the price of input tokens, so
the file being long is a feature: the model gets the whole contract every time and it
costs almost nothing after the first call in each window.

**A blocked draft gets one chance to fix itself.** When the claim checker refuses a draft,
the findings go back to the model and it writes again. This is not the human feedback loop
— that is the approval desk. It is narrower and mechanical: the model wrote something the
product does not do, it is told exactly what and why, and it tries once more. Bounded at
two attempts, because a model that cannot avoid a forbidden claim in two tries is not
going to manage it in five, and the founder should see that rather than a retry bill.

Inert without an API key, like the lead scorer. The service runs, the endpoints answer,
and drafting simply is not available — rather than the whole thing failing to start.
"""
import logging

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.models.content import ContentChannel
from app.services.claims import brand_bible_prompt, check_text, load_voice
from app.services.exceptions import NotConfiguredError

logger = logging.getLogger("astra.mkt.drafting")
settings = get_settings()

#: Two. See the module docstring — this is a ceiling on stubbornness, not on quality.
MAX_ATTEMPTS = 2


class Draft(BaseModel):
    """What the model must return. Every field is something a publisher needs."""

    headline: str | None = Field(
        default=None, max_length=300,
        description="Only for formats that have one — a blog post, an email subject. "
                    "Null for a LinkedIn or X post, where the first line IS the headline.",
    )
    body: str = Field(description="The post itself, ready to publish. No preamble.")
    hashtags: str | None = Field(
        default=None, max_length=300,
        description="Space-separated, at the end, only where the channel uses them.",
    )
    cta: str | None = Field(
        default=None, max_length=200,
        description="One call to action, taken from the approved list.",
    )
    rationale: str = Field(
        max_length=500,
        description="One or two sentences on the angle taken and why it suits this "
                    "reader. Not published — it is what a reviewer reads first to decide "
                    "whether to read the rest.",
    )


class DraftResult:
    def __init__(self, draft: Draft, attempts: int, blocked: bool, findings: list) -> None:
        self.draft = draft
        self.attempts = attempts
        #: True when even the last attempt states something the product does not do. The
        #: caller still stores it — a blocked version is evidence about the prompt, and
        #: throwing it away hides a pattern worth seeing.
        self.blocked = blocked
        self.findings = findings


def channel_brief(channel: ContentChannel) -> str:
    """The channel's own rules, from voice.yaml.

    Read from the file rather than written here so the shape of a LinkedIn post is stated
    once, in the place a person edits, rather than in a prompt string nobody opens.
    """
    channels = load_voice()["channels"]
    key = {
        ContentChannel.LINKEDIN: "linkedin",
        ContentChannel.X: "x",
        ContentChannel.BLOG: "blog",
        ContentChannel.EMAIL: "email",
    }.get(channel)
    if key is None or key not in channels:
        return f"Channel: {channel.value}."

    spec = channels[key]
    lines = [f"CHANNEL: {key}", f"  Length: {spec['length']}"]
    for field in ("hook", "shape", "note", "cadence", "link_placement"):
        if field in spec:
            lines.append(f"  {field.replace('_', ' ').capitalize()}: "
                         f"{' '.join(str(spec[field]).split())}")
    if "hashtags" in spec:
        tags = spec["hashtags"]
        lines.append(f"  Hashtags: {tags['count']}, {tags['placement']}. "
                     f"Choose from: {' '.join(tags['set'])}")
    return "\n".join(lines)


class DraftingAgent:
    @property
    def enabled(self) -> bool:
        return bool(settings.anthropic_api_key)

    async def draft(
        self, *, channel: ContentChannel, brief: str,
        campaign: str | None = None,
    ) -> DraftResult:
        """Write one piece, checking it and correcting once if it is refused."""
        if not self.enabled:
            raise NotConfiguredError("Drafting needs ASTRA_MKT_ANTHROPIC_API_KEY")

        instruction = self._instruction(channel=channel, brief=brief, campaign=campaign)
        correction: str | None = None
        draft: Draft | None = None
        findings: list = []

        for attempt in range(1, MAX_ATTEMPTS + 1):
            draft = await self._generate(instruction, correction)
            result = check_text(" ".join(filter(
                None, [draft.headline, draft.body, draft.cta, draft.hashtags]
            )))
            findings = result.findings

            if not result.blockers:
                logger.info("drafted %s in %d attempt(s), %d warnings",
                            channel.value, attempt, len(result.warnings))
                return DraftResult(draft, attempt, blocked=False, findings=findings)

            logger.warning(
                "draft %d for %s blocked by %s",
                attempt, channel.value, [f.rule for f in result.blockers],
            )
            correction = self._correction(result.blockers)

        return DraftResult(draft, MAX_ATTEMPTS, blocked=True, findings=findings)

    async def revise(
        self, *, channel: ContentChannel, previous: str, feedback: str,
        brief: str | None = None,
    ) -> DraftResult:
        """Rewrite in response to a human.

        Their words go in verbatim between markers. Paraphrasing feedback before acting on
        it is how a revision ends up answering a note nobody wrote.
        """
        if not self.enabled:
            raise NotConfiguredError("Drafting needs ASTRA_MKT_ANTHROPIC_API_KEY")

        instruction = "\n\n".join(filter(None, [
            channel_brief(channel),
            f"THE BRIEF THIS WAS WRITTEN TO:\n{brief}" if brief else None,
            f"WHAT YOU WROTE:\n<draft>\n{previous}\n</draft>",
            f"WHAT THEY ASKED FOR:\n<feedback>\n{feedback}\n</feedback>",
            "Rewrite it. Change what the feedback asks for and leave the rest alone — a "
            "reviewer who asked for one change and got a different post has to start over.",
        ]))

        draft = await self._generate(instruction, None)
        result = check_text(" ".join(filter(
            None, [draft.headline, draft.body, draft.cta, draft.hashtags]
        )))
        return DraftResult(draft, 1, blocked=bool(result.blockers), findings=result.findings)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _instruction(
        self, *, channel: ContentChannel, brief: str, campaign: str | None
    ) -> str:
        return "\n\n".join(filter(None, [
            channel_brief(channel),
            f"CAMPAIGN: {campaign}" if campaign else None,
            f"WRITE THIS:\n{brief}",
        ]))

    @staticmethod
    def _correction(blockers: list) -> str:
        """Tell the model exactly what it got wrong, and what is true instead.

        Naming the true version matters more than naming the error: a model told only to
        stop saying something reaches for a synonym.
        """
        lines = [
            "Your last draft claimed things ASTRA does not do. Each one, with the truth "
            "to use instead:",
        ]
        for finding in blockers:
            lines.append(f'  - You wrote "{finding.matched}". {finding.guidance}')
        lines.append(
            "Rewrite it without those claims. Do not substitute a synonym for the same "
            "idea — the idea itself is false."
        )
        return "\n".join(lines)

    async def _generate(self, instruction: str, correction: str | None) -> Draft:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.with_options(timeout=120.0).messages.parse(
            model=settings.drafting_model,
            max_tokens=8192,
            # A list of blocks, with the breakpoint after the Brand Bible: everything
            # stable is cached, and the varying instruction sits outside the cached prefix.
            system=[{
                "type": "text",
                "text": brand_bible_prompt(),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": instruction if correction is None
                else f"{instruction}\n\n{correction}",
            }],
            output_format=Draft,
        )
        return response.parsed_output
