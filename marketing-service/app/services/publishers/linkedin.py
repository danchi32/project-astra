"""Post to the ASTRA company page.

Two details in LinkedIn's API do real damage if you get them wrong, and both are the kind
that look fine in testing and mangle text in production.

**`commentary` is not plain text — it is "little" format.** Fifteen characters are
reserved, and the docs are explicit that they must be escaped *"even if those characters
are not used in one of the supported elements"*. Unescaped, a post containing `(3 min
read)` or `snake_case` or `C:\\Windows` renders wrong, and the failure is silent: LinkedIn
accepts it and publishes the mess. So every character of the approved body is escaped
here, one pass, backslash included — which is why the escape runs character by character
rather than as a sequence of replacements that would double-escape each other's output.

**Hashtags are the deliberate exception.** Escaping `#` would turn `#ITOps` into literal
text, so the tags from the draft are emitted as `{hashtag|\\#|ITOps}` templates instead,
which is what makes them clickable. Escaping everything would have been simpler and would
have quietly cost every post its hashtags.

Also worth knowing before this ever runs: LinkedIn access tokens last 60 days, and
programmatic refresh is available only to approved Marketing Developer Platform partners.
Everyone else re-authorises through a browser. The token here is therefore treated as
something that WILL expire — a 401 says so in the logs in those words, rather than as a
generic auth failure someone has to go and decode.
"""
import json
import logging
import re

import httpx

from app.core.config import get_settings
from app.models.content import ContentVersion
from app.services.publishers.base import PublisherError, PublishResult

logger = logging.getLogger("astra.mkt.publish.linkedin")
settings = get_settings()

_API = "https://api.linkedin.com/rest/posts"

#: Every character "little" treats as markup. From the format's own grammar. The backslash
#: is in here too, and it is the reason this is applied per character: replacing "\" after
#: replacing "(" would escape the backslashes the earlier pass just added.
_RESERVED = set("\\|{}@[]()<>#*_~")

#: LinkedIn's published ceiling for a post. We refuse rather than truncate — a post cut
#: off mid-sentence in public is worse than an error someone can act on.
MAX_COMMENTARY = 3000

_HASHTAG = re.compile(r"#?([A-Za-z0-9_]+)")


def escape_little(text: str) -> str:
    """Escape every reserved character, per the little text format grammar."""
    out: list[str] = []
    for char in text:
        if char in _RESERVED:
            out.append("\\")
        out.append(char)
    return "".join(out)


def hashtag_template(tag: str) -> str:
    """`#ITOps` -> `{hashtag|\\#|ITOps}`.

    The template is what makes a tag clickable. A bare escaped `\\#ITOps` renders as the
    four visible characters and follows nothing.
    """
    match = _HASHTAG.fullmatch(tag.strip())
    if match is None:
        # Not a valid tag (spaces, punctuation). Emitted as escaped text rather than
        # dropped, so a malformed tag is visible in the post and gets fixed, not silently
        # swallowed.
        return escape_little(tag.strip())
    return "{hashtag|\\#|" + match.group(1) + "}"


def _already_says(body: str, cta: str) -> bool:
    """Is this call to action already in the body?

    Compared with punctuation and case removed, because "Book an assessment." in the body
    and "Book an assessment" in the field are the same sentence to a reader and different
    strings to everything else.
    """
    def normalise(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    return normalise(cta) in normalise(body)


class LinkedInPublisher:
    channel_name = "linkedin"

    @property
    def enabled(self) -> bool:
        return bool(settings.linkedin_access_token and settings.linkedin_organization_id)

    @property
    def author_urn(self) -> str:
        return f"urn:li:organization:{settings.linkedin_organization_id}"

    def render(self, version: ContentVersion) -> str:
        """Build the exact commentary string that will be transmitted.

        Pure and side-effect free, so the dry run and the approval preview can show a
        person the real thing rather than an approximation of it.
        """
        body = version.body.strip()
        parts = [escape_little(body)]

        # Only if the body has not already said it. The drafting agent is told to keep the
        # CTA out of the body, but an instruction is not a guarantee, and a post that ends
        # with the same sentence twice is the kind of mistake a reader remembers. Caught
        # on the very first real draft, by the preview, before anything was public.
        if version.cta and not _already_says(body, version.cta):
            parts.append(escape_little(version.cta.strip()))

        if version.hashtags:
            tags = [hashtag_template(t) for t in version.hashtags.split() if t.strip()]
            if tags:
                parts.append(" ".join(tags))

        # A blank line between blocks: LinkedIn renders \n literally, and a CTA jammed
        # against the last sentence is how an automated post announces that it is one.
        return "\n\n".join(parts)

    async def publish(self, version: ContentVersion) -> PublishResult:
        if not self.enabled:
            raise PublisherError(
                "LinkedIn is not configured "
                "(ASTRA_MKT_LINKEDIN_ACCESS_TOKEN, ASTRA_MKT_LINKEDIN_ORGANIZATION_ID)"
            )

        commentary = self.render(version)
        if len(commentary) > MAX_COMMENTARY:
            raise PublisherError(
                f"The post is {len(commentary)} characters after escaping; LinkedIn "
                f"accepts {MAX_COMMENTARY}. Shorten it — this is not truncated for you."
            )

        payload = {
            "author": self.author_urn,
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    _API,
                    content=json.dumps(payload),
                    headers={
                        "Authorization": f"Bearer {settings.linkedin_access_token}",
                        "X-Restli-Protocol-Version": "2.0.0",
                        "LinkedIn-Version": settings.linkedin_api_version,
                        "Content-Type": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            raise PublisherError(f"Could not reach LinkedIn: {exc}", retryable=True) from exc

        if response.status_code != 201:
            raise self._error_for(response)

        # The created post's URN comes back in a header, not the body.
        ref = response.headers.get("x-restli-id")
        if not ref:
            # Published, but we cannot say what. Loud, because the post is live and the
            # only record of it is now LinkedIn's own page.
            logger.error(
                "LinkedIn returned 201 with no x-restli-id; a post is live and unidentified"
            )
            raise PublisherError("LinkedIn accepted the post but returned no id")

        logger.info("published %s to LinkedIn as %s", version.id, ref)
        return PublishResult(ref=ref, url=self.post_url(ref), rendered=commentary)

    @staticmethod
    def post_url(ref: str) -> str:
        return f"https://www.linkedin.com/feed/update/{ref}/"

    @staticmethod
    def _error_for(response: httpx.Response) -> PublisherError:
        """Turn LinkedIn's status into something a person can act on.

        The two that will actually happen are called out by name. A 401 here almost always
        means the 60-day token quietly expired, and "unauthorized" alone sends whoever
        reads it looking for a permissions problem that is not there.
        """
        body = response.text[:400]
        if response.status_code == 401:
            return PublisherError(
                "LinkedIn rejected the token. These expire after 60 days and, unless the "
                "app is an approved Marketing Developer Platform partner, must be renewed "
                f"through the browser OAuth flow. ({body})"
            )
        if response.status_code == 403:
            return PublisherError(
                "LinkedIn refused: the token lacks w_organization_social, or the member "
                f"who authorised it is no longer an admin of the page. ({body})"
            )
        if response.status_code == 429:
            return PublisherError(f"LinkedIn rate limit ({body})", retryable=True)
        if response.status_code >= 500:
            return PublisherError(f"LinkedIn error {response.status_code} ({body})",
                                  retryable=True)
        return PublisherError(f"LinkedIn refused with {response.status_code}: {body}")
