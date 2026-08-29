"""What every publisher must be, and what it must never do.

A publisher turns an approved version into a live post on someone else's platform. That
makes it the one component in this service whose mistakes are *public and irreversible*,
so the contract is narrow on purpose:

* A publisher never reads the content tables and never decides whether to publish. It is
  handed words and told to post them. The gate lives in `app/services/publishing.py`, in
  one place, so there is no second implementation to keep honest.
* A publisher never truncates. If the copy will not fit the platform, it refuses. Half a
  post in public is worse than no post, and worse than an error a person can act on.
* A publisher returns the platform's own id and URL, because "did this actually go out"
  must be answerable later without logging into anything.
"""
from dataclasses import dataclass
from typing import Protocol

from app.models.content import ContentVersion


class PublisherError(Exception):
    """The platform refused, or could not be reached.

    Distinct from PublishRefused, which means *we* refused. Keeping them separate matters
    when reading an incident later: one says the gate worked, the other says LinkedIn was
    down or the token had expired.
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        #: True for 429/5xx/timeouts — conditions where the same request may succeed
        #: later. False for 401/403/400, where retrying only repeats the mistake.
        self.retryable = retryable


@dataclass(frozen=True)
class PublishResult:
    #: The platform's identifier, stored so a post can be found again from our side.
    ref: str
    #: A URL a human can open. Not always derivable from the ref, so the publisher builds it.
    url: str | None = None
    #: What was actually transmitted, after platform-specific rendering. Recorded because
    #: "what did we send" and "what did we approve" are different questions once escaping
    #: and templating are involved.
    rendered: str | None = None


class Publisher(Protocol):
    channel_name: str

    @property
    def enabled(self) -> bool:
        """False when unconfigured. An unconfigured publisher must not raise on import —
        the service runs with none of them set up."""
        ...

    def render(self, version: ContentVersion) -> str:
        """Exactly what will be transmitted. Pure, so it can be shown to a human first."""
        ...

    async def publish(self, version: ContentVersion) -> PublishResult:
        ...
