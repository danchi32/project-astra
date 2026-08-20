"""Wire types for the support chatbot — the portal widget and the website widget.

One pair of schemas for both, because the two widgets ask the same question and render the
same answer; what differs is who is allowed to call, and that is settled by the endpoint,
not by the payload. Nothing here identifies an organization: the portal's scope comes from
the caller's token, and the public endpoint has none. A body that could name an org would
be a body that could ask for someone else's.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AssistantTurn(BaseModel):
    """One prior turn, replayed by the client.

    These widgets persist nothing server-side, so the transcript arrives from the browser
    and is untrusted input: the length caps here are the first line of defence against a
    client that pads the history to run up an AI bill.
    """
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantAsk(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    #: Only the tail is used (see `support_bot._HISTORY_TURNS`); the cap is here so an
    #: oversized body is rejected before it is parsed rather than quietly truncated.
    history: list[AssistantTurn] = Field(default_factory=list, max_length=20)


class AssistantSource(BaseModel):
    """A document the answer came from.

    `article_id` is present only for ASTRA help centre articles, which a signed-in user can
    open. FAQ entries and an organization's own runbooks have no page to link to, so the
    UI shows the title alone rather than a dead link.
    """
    model_config = ConfigDict(from_attributes=True)

    title: str
    kind: Literal["help", "knowledge", "faq"]
    article_id: str | None = None


class AssistantReply(BaseModel):
    answer: str
    sources: list[AssistantSource] = Field(default_factory=list)
    #: False when the documentation did not cover the question. The widgets read this to
    #: surface the human path — a support request, or the contact form.
    grounded: bool = True
