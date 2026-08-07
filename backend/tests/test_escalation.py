"""Handing an unsolved problem to a human.

Almost everything pinned here is a refusal. The feature's value is that it files ONE
well-evidenced ticket after asking — and every failure mode is a version of filing more
than that, or filing without asking, or telling the user a ticket exists when it doesn't.
"""
import uuid

import pytest

from app.models import Conversation, Message, MessageRole, SupportEscalation
from app.models.support_escalation import EscalationState
from app.services.support.connector import MockConnector, TicketRequest
from app.services.support.dossier import Attempt, Dossier
from app.services.support.escalation import ConsentMissing, EscalationService


def _dossier(problem: str = "my laptop is very slow", **kw) -> Dossier:
    return Dossier(problem=problem, hostname="DESKTOP-TEST", **kw)


async def _conversation(session, org_id, device_id=None) -> Conversation:
    convo = Conversation(org_id=org_id, device_id=device_id, title="chat")
    session.add(convo)
    await session.flush()
    return convo


async def _user_says(session, convo, text="haan") -> None:
    session.add(Message(conversation_id=convo.id, role=MessageRole.USER, content=text))
    await session.flush()


# ── Consent, enforced in code ──────────────────────────────────────────────


async def test_raising_without_an_offer_is_refused(session_factory, admin_user):
    """The model must not be able to file into a customer's production queue on its own.
    A prompt saying "always ask first" is a request; this is the rule."""
    async with session_factory() as session:
        convo = await _conversation(session, admin_user.org_id)
        svc = EscalationService(session, connector=MockConnector())
        with pytest.raises(ConsentMissing):
            await svc.raise_ticket(
                org_id=admin_user.org_id, conversation_id=convo.id,
                requester_email="u@acme.com",
            )


async def test_raising_before_the_user_answers_is_refused(session_factory, admin_user):
    """The gate that actually matters. Without it the model could call offer and raise back
    to back and never leave room for a person to say no."""
    async with session_factory() as session:
        convo = await _conversation(session, admin_user.org_id)
        svc = EscalationService(session, connector=MockConnector())
        await svc.offer(
            org_id=admin_user.org_id, conversation_id=convo.id, device_id=None,
            user_id=admin_user.id, dossier=_dossier(),
        )
        with pytest.raises(ConsentMissing):
            await svc.raise_ticket(
                org_id=admin_user.org_id, conversation_id=convo.id,
                requester_email="u@acme.com",
            )


async def test_after_the_user_answers_the_ticket_is_raised(session_factory, admin_user):
    connector = MockConnector()
    async with session_factory() as session:
        convo = await _conversation(session, admin_user.org_id)
        svc = EscalationService(session, connector=connector)
        _, question = await svc.offer(
            org_id=admin_user.org_id, conversation_id=convo.id, device_id=None,
            user_id=admin_user.id, dossier=_dossier(),
        )
        assert "?" in question, "the offer has to actually be a question"

        await _user_says(session, convo)
        outcome = await svc.raise_ticket(
            org_id=admin_user.org_id, conversation_id=convo.id,
            requester_email="priya@acme.com",
        )
        await session.commit()

    assert outcome.created
    assert outcome.escalation.state is EscalationState.RAISED
    assert outcome.escalation.external_ticket_id
    assert "#" in outcome.message and "support" in outcome.message.lower()
    assert connector.requests[0].requester_email == "priya@acme.com"


async def test_declining_closes_the_offer(session_factory, admin_user):
    async with session_factory() as session:
        convo = await _conversation(session, admin_user.org_id)
        svc = EscalationService(session, connector=MockConnector())
        await svc.offer(org_id=admin_user.org_id, conversation_id=convo.id, device_id=None,
                        user_id=admin_user.id, dossier=_dossier())
        await svc.decline(conversation_id=convo.id)
        await _user_says(session, convo, "nahi rehne do")
        with pytest.raises(ConsentMissing):
            await svc.raise_ticket(org_id=admin_user.org_id, conversation_id=convo.id,
                                   requester_email="u@acme.com")


# ── One problem, one ticket ────────────────────────────────────────────────


async def test_reporting_the_same_problem_again_does_not_open_a_second_ticket(
    session_factory, admin_user
):
    """The failure that kills this feature. A user reports, nothing visibly happens, they
    report again — and the customer's queue fills with duplicates until IT switches the
    integration off."""
    device_id = uuid.uuid4()
    connector = MockConnector()

    async with session_factory() as session:
        convo = await _conversation(session, admin_user.org_id, device_id)
        svc = EscalationService(session, connector=connector)
        await svc.offer(org_id=admin_user.org_id, conversation_id=convo.id,
                        device_id=device_id, user_id=admin_user.id,
                        dossier=_dossier("my laptop is very slow"))
        await _user_says(session, convo)
        first = await svc.raise_ticket(org_id=admin_user.org_id, conversation_id=convo.id,
                                       requester_email="p@acme.com")
        await session.commit()

    async with session_factory() as session:
        convo2 = await _conversation(session, admin_user.org_id, device_id)
        svc = EscalationService(session, connector=connector)
        escalation, message = await svc.offer(
            org_id=admin_user.org_id, conversation_id=convo2.id, device_id=device_id,
            user_id=admin_user.id, dossier=_dossier("laptop is very slow still"),
        )
        await session.commit()

    assert escalation is None, "a second offer must not even be made"
    assert first.escalation.external_ticket_id in message
    assert len(connector.requests) == 1


async def test_a_different_problem_on_the_same_device_still_opens_a_ticket(
    session_factory, admin_user
):
    """Dedupe must not become a gag. Two unrelated faults on one laptop are two tickets."""
    device_id = uuid.uuid4()
    connector = MockConnector()

    async with session_factory() as session:
        convo = await _conversation(session, admin_user.org_id, device_id)
        svc = EscalationService(session, connector=connector)
        await svc.offer(org_id=admin_user.org_id, conversation_id=convo.id,
                        device_id=device_id, user_id=admin_user.id,
                        dossier=_dossier("my laptop is very slow"))
        await _user_says(session, convo)
        await svc.raise_ticket(org_id=admin_user.org_id, conversation_id=convo.id,
                               requester_email="p@acme.com")
        await session.commit()

    async with session_factory() as session:
        convo2 = await _conversation(session, admin_user.org_id, device_id)
        svc = EscalationService(session, connector=connector)
        escalation, _ = await svc.offer(
            org_id=admin_user.org_id, conversation_id=convo2.id, device_id=device_id,
            user_id=admin_user.id,
            dossier=_dossier("printer will not print anything"),
        )
        await _user_says(session, convo2)
        await svc.raise_ticket(org_id=admin_user.org_id, conversation_id=convo2.id,
                               requester_email="p@acme.com")
        await session.commit()

    assert escalation is not None
    assert len(connector.requests) == 2


async def test_another_persons_ticket_does_not_suppress_yours(session_factory, admin_user,
                                                              user_headers, other_org):
    """A problem belongs to a person and a machine, not to the organization. Suppressing
    across an org would hide real tickets from real people."""
    connector = MockConnector()
    mine, theirs = uuid.uuid4(), uuid.uuid4()

    async with session_factory() as session:
        svc = EscalationService(session, connector=connector)
        for device in (mine, theirs):
            convo = await _conversation(session, admin_user.org_id, device)
            await svc.offer(org_id=admin_user.org_id, conversation_id=convo.id,
                            device_id=device, user_id=admin_user.id,
                            dossier=_dossier("my laptop is very slow"))
            await _user_says(session, convo)
            await svc.raise_ticket(org_id=admin_user.org_id, conversation_id=convo.id,
                                   requester_email="p@acme.com")
        await session.commit()

    assert len(connector.requests) == 2


# ── Never claim a ticket that doesn't exist ────────────────────────────────


async def test_a_helpdesk_outage_is_reported_honestly(session_factory, admin_user):
    """The single worst outcome: telling someone their problem is with IT when nothing was
    filed. They stop chasing it and wait for a reply nobody will write."""
    async with session_factory() as session:
        convo = await _conversation(session, admin_user.org_id)
        svc = EscalationService(session, connector=MockConnector(fail_with="503 from helpdesk"))
        await svc.offer(org_id=admin_user.org_id, conversation_id=convo.id, device_id=None,
                        user_id=admin_user.id, dossier=_dossier())
        await _user_says(session, convo)
        outcome = await svc.raise_ticket(org_id=admin_user.org_id, conversation_id=convo.id,
                                         requester_email="p@acme.com")
        await session.commit()

    assert not outcome.created
    assert outcome.escalation.state is EscalationState.FAILED
    assert "couldn't reach" in outcome.message.lower()
    assert "raised" not in outcome.message.lower().split("isn't raised")[0]
    assert outcome.escalation.last_error


async def test_an_unconfigured_org_is_told_so_rather_than_promised_a_ticket(
    session_factory, admin_user
):
    """No connector means no helpdesk connected yet — inert, like every other integration
    here. The user still gets a true sentence."""
    async with session_factory() as session:
        convo = await _conversation(session, admin_user.org_id)
        svc = EscalationService(session, connector=None)
        await svc.offer(org_id=admin_user.org_id, conversation_id=convo.id, device_id=None,
                        user_id=admin_user.id, dossier=_dossier())
        await _user_says(session, convo)
        outcome = await svc.raise_ticket(org_id=admin_user.org_id, conversation_id=convo.id,
                                         requester_email="p@acme.com")
        await session.commit()

    assert not outcome.created
    assert outcome.escalation.state is EscalationState.FAILED
    assert "no helpdesk" in outcome.message.lower()


async def test_a_failed_escalation_can_be_retried_later(session_factory, admin_user):
    """A helpdesk outage must not permanently swallow the problem — the next offer works."""
    async with session_factory() as session:
        convo = await _conversation(session, admin_user.org_id)
        svc = EscalationService(session, connector=MockConnector(fail_with="down"))
        await svc.offer(org_id=admin_user.org_id, conversation_id=convo.id, device_id=None,
                        user_id=admin_user.id, dossier=_dossier())
        await _user_says(session, convo)
        await svc.raise_ticket(org_id=admin_user.org_id, conversation_id=convo.id,
                               requester_email="p@acme.com")
        await session.commit()

    async with session_factory() as session:
        convo2 = await _conversation(session, admin_user.org_id)
        svc = EscalationService(session, connector=MockConnector())
        escalation, _ = await svc.offer(org_id=admin_user.org_id, conversation_id=convo2.id,
                                        device_id=None, user_id=admin_user.id,
                                        dossier=_dossier())
        await _user_says(session, convo2)
        outcome = await svc.raise_ticket(org_id=admin_user.org_id,
                                         conversation_id=convo2.id,
                                         requester_email="p@acme.com")
        await session.commit()

    assert escalation is not None and outcome.created


# ── The dossier ────────────────────────────────────────────────────────────


def test_the_dossier_carries_the_users_words_and_what_was_tried():
    """The reason this beats an ordinary ticket. A technician should not have to redo the
    investigation ASTRA already did."""
    d = Dossier(
        problem="mera laptop bahut slow hai",
        hostname="DESKTOP-HRIUG3P", os_version="Windows 11 Enterprise 25H2",
        facts=[("RAM", "94% for 3 days"), ("Chrome", "4.2 GB")],
        attempts=[
            Attempt("Clear temporary files", True, "Freed 1.2 GB, no change"),
            Attempt("Restart Windows Explorer", True, "No change"),
        ],
        device_url="https://astra.example/devices/abc",
    )
    out = d.to_html()
    assert "mera laptop bahut slow hai" in out
    assert "Freed 1.2 GB" in out
    assert "94% for 3 days" in out
    assert "No matching runbook" in out
    assert "devices/abc" in out


def test_no_applicable_fix_is_stated_rather_than_left_blank():
    """"Nothing was tried" and "no automatic fix exists for this" read identically as an
    empty section, and they mean very different things to whoever picks the ticket up."""
    assert "No automatic fix applies" in Dossier(problem="x").to_html()


def test_the_subject_leads_with_the_users_own_words():
    """It is what they will say on the phone when they chase it."""
    subject = Dossier(problem="outlook khul nahi raha", hostname="PC-1").subject()
    assert subject.startswith("[ASTRA] outlook khul nahi raha")
    assert "PC-1" in subject


def test_user_text_cannot_inject_html_into_the_ticket():
    """The description is rendered as HTML in someone else's helpdesk. Whatever a user
    types goes in there verbatim, so it has to be escaped."""
    out = Dossier(problem="<script>alert(1)</script>").to_html()
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_a_ticket_is_tagged_so_the_customer_can_report_on_it():
    """Their reporting has to be able to answer "how many did ASTRA raise" — that number
    is the renewal conversation."""
    assert "astra" in TicketRequest(
        requester_email="a@b.com", subject="s", description_html="d"
    ).tags
