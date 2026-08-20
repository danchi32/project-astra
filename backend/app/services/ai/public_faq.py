"""The public FAQ the website chatbot answers from.

Kept here, next to the retrieval code, rather than fetched from the marketing site: the
site is a static export on shared hosting with no API, and the assistant must never be
left grounding its answers on whatever HTML it happened to scrape. These entries are the
sales-side facts — price shape, trial, plans, hardware, contact — that the help centre
articles deliberately do not cover, because those are written for customers who already
have an account.

Retrieval here is lexical, not semantic. The corpus is a dozen short entries whose wording
we control, and a word-overlap score over that is both free and predictable — where an
embedding call would add a network round trip to every message a visitor sends. Help
centre articles keep their semantic search; this is only the FAQ half.
"""
from dataclasses import dataclass

from app.services.ai.embeddings import normalise


@dataclass(frozen=True)
class FaqEntry:
    question: str
    answer: str
    #: Words a visitor might use that appear in neither the question nor the answer.
    #: Without them "cost" scores zero against an entry that only ever says "priced".
    keywords: tuple[str, ...] = ()

    def haystack(self) -> str:
        return f"{self.question} {self.answer} {' '.join(self.keywords)}"


#: Every claim here has to be one the website already makes. A chatbot that invents a
#: price or a certification is worse than one that says "I don't know" — so when a fact
#: changes on the site, it changes here in the same commit.
PUBLIC_FAQ: tuple[FaqEntry, ...] = (
    FaqEntry(
        question="What is ASTRA?",
        answer=(
            "ASTRA is an AI System Administrator for Windows fleets, built by Technomate IT "
            "Solution. A lightweight Windows agent streams telemetry — CPU, RAM, disk, event "
            "logs, running apps, services and Windows Update status — back to the platform, "
            "and the AI engine reasons over that evidence to diagnose problems and fix them."
        ),
        keywords=("astra", "product", "overview", "platform", "software"),
    ),
    FaqEntry(
        question="How does ASTRA fix problems on its own?",
        answer=(
            "Every remediation is allowlisted and falls into one of three tiers. Automatic "
            "fixes — restarting Explorer, Outlook, Teams or Zoom, flushing DNS, clearing temp "
            "files, restarting a network adapter — run on their own. Riskier ones, such as an "
            "Office repair or a driver update, wait for IT approval. Registry, firmware and "
            "reinstall-level actions are admin-only. The tiers are enforced in the backend, "
            "never only in the AI's prompt."
        ),
        keywords=("self healing", "selfhealing", "remediation", "automate", "automatic",
                  "approval", "tiers", "guardrails", "risky"),
    ),
    FaqEntry(
        question="How is ASTRA priced?",
        answer=(
            "Per device, per month. Essential covers inventory, telemetry and patching; "
            "Professional adds the AI engine and automatic self-healing; Expert adds "
            "compliance, fleet-wide remediation and full audit. Annual billing saves about "
            "17%. For fleets above 50 devices, contact sales for volume pricing."
        ),
        keywords=("cost", "costs", "price", "pricing", "expensive", "seat", "licence",
                  "license", "subscription", "billing", "quote", "rate"),
    ),
    FaqEntry(
        question="Which plan should I choose?",
        answer=(
            "Most teams start on Professional — that is where the AI actually fixes issues on "
            "its own. Essential suits you if you mainly need visibility and patching, and "
            "Expert if you have compliance or audit requirements. You can upgrade or downgrade "
            "at any time; billing adjusts on the next cycle based on your active devices."
        ),
        keywords=("plan", "plans", "tier", "essential", "professional", "expert", "upgrade",
                  "downgrade", "compare", "difference"),
    ),
    FaqEntry(
        question="Is there a free trial?",
        answer=(
            "Yes — you can start a free trial, and no credit card is needed to explore the "
            "platform. Sign up on the ASTRA portal and enrol your first device with the "
            "installer the portal generates for you."
        ),
        keywords=("trial", "free", "try", "evaluate", "poc", "pilot", "card"),
    ),
    FaqEntry(
        question="How do I book a demo or talk to sales?",
        answer=(
            "Use the Book a demo button at the top of any page, or the contact form on the "
            "Contact page. You can also email sales@technomateai.com or call "
            "+91 97115 31786 (Mon-Sat, 10:00 AM - 7:00 PM IST)."
        ),
        keywords=("demo", "sales", "contact", "call", "email", "phone", "meeting", "human",
                  "person", "reach", "speak", "someone"),
    ),
    FaqEntry(
        question="What do I need to run ASTRA?",
        answer=(
            "Windows devices and outbound HTTPS. The agent installs as a Windows service plus "
            "a tray app, enrols with a token the portal issues, and starts reporting within a "
            "minute. There is nothing to host — the portal and API are managed for you."
        ),
        keywords=("requirements", "supported", "windows", "mac", "linux", "install", "setup",
                  "deploy", "premise", "onprem", "cloud", "agent", "server"),
    ),
    FaqEntry(
        question="How long does rollout take?",
        answer=(
            "A single device is enrolled in minutes with the generated installer. For a fleet, "
            "the same installer is deployed through Intune, Group Policy or your existing "
            "software distribution, and devices appear in the portal as they check in."
        ),
        keywords=("rollout", "deployment", "intune", "gpo", "group policy", "onboarding",
                  "fleet", "bulk", "mass"),
    ),
    FaqEntry(
        question="Is my data secure?",
        answer=(
            "The platform is built on least privilege: role-based access control on every API, "
            "short-lived tokens, HTTPS everywhere, encryption in transit and at rest, and an "
            "audit log entry for every change and every command sent to a device. The agent "
            "only ever executes allowlisted, approved actions."
        ),
        keywords=("security", "secure", "privacy", "gdpr", "data", "compliance", "audit",
                  "encryption", "safe", "trust", "breach"),
    ),
    FaqEntry(
        question="What happens when someone leaves the company?",
        answer=(
            "Secure offboarding locks down the leaver's account and forces them out of their "
            "active Windows session in one click — not just at next login — and the whole "
            "action is audited."
        ),
        keywords=("offboarding", "leaver", "resign", "termination", "disable", "sign out",
                  "exit", "employee"),
    ),
    FaqEntry(
        question="Do you supply hardware as well?",
        answer=(
            "Yes. Technomate IT Solution is also a laptop and hardware supplier, and devices "
            "can be bundled with ASTRA for a fully managed rollout. Managed IT services are "
            "available alongside both."
        ),
        keywords=("hardware", "laptop", "laptops", "buy", "supply", "procurement", "devices",
                  "managed services", "amc", "desktop"),
    ),
    FaqEntry(
        question="Where is Technomate based?",
        answer=(
            "Technomate IT Solution is in Ayodhya Ganj, Dadri, Greater Noida, Uttar Pradesh "
            "203207, India. Office hours are Mon-Sat, 10:00 AM - 7:00 PM IST."
        ),
        keywords=("address", "location", "office", "india", "noida", "company", "about",
                  "hours", "timing", "based"),
    ),
    FaqEntry(
        question="I already use ASTRA and need help with my account",
        answer=(
            "Sign in to the ASTRA portal at astra.technomateai.com — Help & support there has "
            "the full guides, the in-portal assistant, and a form that raises a request with "
            "our team. You can also email astra@technomateai.com."
        ),
        keywords=("login", "sign in", "portal", "customer", "support", "account", "password",
                  "ticket", "existing"),
    ),
)

#: Below this the best entry is not about the question — it merely shares a common word.
#: Scored against the corpus above, a genuine hit ("how much does it cost") lands near
#: 0.4, while an unrelated sentence rarely clears 0.1.
_MIN_SCORE = 0.18


def search_faq(query: str, *, limit: int = 3) -> list[FaqEntry]:
    """The FAQ entries a question is actually about, best first.

    Scored by how much of the *question* is covered, not how much of the entry: a long
    answer must not be penalised for containing words the visitor did not type.
    """
    wanted = set(normalise(query))
    if not wanted:
        return []

    scored: list[tuple[float, int, FaqEntry]] = []
    for index, entry in enumerate(PUBLIC_FAQ):
        overlap = wanted & set(normalise(entry.haystack()))
        score = len(overlap) / len(wanted)
        if score >= _MIN_SCORE:
            # `index` keeps the sort total and stable — FaqEntry is not orderable, so two
            # entries tying on score would otherwise raise rather than pick one.
            scored.append((score, index, entry))

    scored.sort(key=lambda triple: (-triple[0], triple[1]))
    return [entry for _, _, entry in scored[:limit]]
