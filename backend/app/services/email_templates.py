"""Rendering for the org-customizable asset-assignment email.

The org authors a **plain-text** subject and body with `{{placeholders}}`. We substitute
the values, HTML-escape everything (so an asset name can never inject markup), wrap it in
the branded shell, and add the "Acknowledge receipt" button — positioned at
`{{acknowledge_button}}` if the author placed it, otherwise appended.
"""
from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass

import nh3


@dataclass(frozen=True)
class PlaceholderSpec:
    """One placeholder the org can put in the template.

    Everything the editor needs to describe a placeholder lives here — its label, which
    group it belongs to, the value the preview shows, and whether it depends on a linked
    device. That last flag used to be a hardcoded list in the portal as well as a comment
    here, and the two drifted: the editor previewed device fields with sample values for
    assets that had no device, so a template looked complete and the real email went out
    with holes in it. One definition, read by both sides, is the fix.
    """

    key: str
    label: str
    group: str          # assignee | asset | device | org
    sample: str         # what the editor's preview substitutes
    needs_device: bool = False


#: Human titles for the groups, in the order the editor should show them.
PLACEHOLDER_GROUPS: list[tuple[str, str]] = [
    ("assignee", "The person it's assigned to"),
    ("asset", "The asset record"),
    ("device", "The linked device"),
    ("org", "Your organization"),
]

#: Every placeholder the assignment email can carry.
#:
#: `employee_name` is the assignee ("name of user"); `device_user` is the account currently
#: signed in on the linked device ("User") — different people, often enough to matter.
#:
#: `manufacturer`, `model`, `brand_model` and `serial` are in the asset group rather than
#: the device group on purpose: each reads the asset's own field first and only falls back
#: to the device, so they still resolve for a monitor or phone that no agent reports on.
ASSET_PLACEHOLDER_SPECS: list[PlaceholderSpec] = [
    PlaceholderSpec("employee_name", "Full name", "assignee", "Sam Rivera"),
    PlaceholderSpec("employee_email", "Email address", "assignee", "sam.rivera@acme.com"),

    PlaceholderSpec("asset_name", "Name", "asset", "Dell Latitude 7440"),
    PlaceholderSpec("asset_tag", "Asset tag", "asset", "AST-001"),
    PlaceholderSpec("category", "Category", "asset", "laptop"),
    PlaceholderSpec("status", "Status", "asset", "in use"),
    PlaceholderSpec("brand_model", "Make and model", "asset", "Dell Latitude 7440"),
    PlaceholderSpec("manufacturer", "Make", "asset", "Dell"),
    PlaceholderSpec("model", "Model", "asset", "Latitude 7440"),
    PlaceholderSpec("serial", "Serial number", "asset", "5CD1234XYZ"),
    PlaceholderSpec("location", "Location", "asset", "Mumbai HQ — 3rd floor"),
    PlaceholderSpec("purchase_date", "Purchase date", "asset", "2025-04-12"),
    PlaceholderSpec("warranty_expiry", "Warranty expires", "asset", "2028-04-11"),
    # No currency symbol: the org's currency isn't recorded anywhere, so printing one would
    # be a guess. Authors write their own ("₹{{purchase_cost}}").
    PlaceholderSpec("purchase_cost", "Purchase cost (no symbol)", "asset", "84999"),
    PlaceholderSpec("notes", "Notes", "asset", "Includes charger and sleeve"),
    PlaceholderSpec("assigned_on", "Date assigned", "asset", "2026-08-10"),

    PlaceholderSpec("hostname", "Hostname", "device", "LAPTOP-SAM", needs_device=True),
    PlaceholderSpec("os_version", "Operating system", "device", "Windows 11 Pro 23H2", needs_device=True),
    PlaceholderSpec("cpu", "Processor", "device", "Intel Core i7-1365U", needs_device=True),
    PlaceholderSpec("ram", "Memory", "device", "16 GB", needs_device=True),
    PlaceholderSpec("storage", "Storage", "device", "512 GB", needs_device=True),
    PlaceholderSpec("software", "Installed apps", "device", "142 apps", needs_device=True),
    PlaceholderSpec("device_user", "Signed-in user", "device", "ACME\\sam", needs_device=True),
    PlaceholderSpec("device_last_seen", "Last checked in", "device", "2026-08-10 14:32 UTC", needs_device=True),
    PlaceholderSpec("agent_version", "ASTRA agent version", "device", "0.7.3", needs_device=True),

    PlaceholderSpec("org_name", "Organization name", "org", "Your Company"),
]

#: Flat key list — what the renderer fills and what older clients read.
ASSET_PLACEHOLDERS = [spec.key for spec in ASSET_PLACEHOLDER_SPECS]

_ACK_MARKER = "{{acknowledge_button}}"
_TOKEN = re.compile(r"\{\{(\w+)\}\}")


def placeholder_groups() -> list[tuple[str, str, list[PlaceholderSpec]]]:
    """(key, title, specs) in display order — what the editor renders its picker from."""
    return [
        (key, title, [s for s in ASSET_PLACEHOLDER_SPECS if s.group == key])
        for key, title in PLACEHOLDER_GROUPS
    ]

DEFAULT_ASSET_SUBJECT = "Please confirm receipt of {{asset_name}}"
DEFAULT_ASSET_BODY = (
    "Hi {{employee_name}},\n\n"
    "{{org_name}} has assigned the following asset to you:\n\n"
    "{{asset_name}}\n\n"
    "Please confirm you've received it using the button below. "
    "If you didn't expect this, contact your IT team."
)


def _shell(title: str, body_html: str) -> str:
    return f"""<div style="font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#111">
      <div style="font-size:22px;font-weight:700;color:#2563eb;margin-bottom:8px">⬡ ASTRA</div>
      <h1 style="font-size:18px;margin:0 0 16px">{title}</h1>
      {body_html}
    </div>"""


def _button_anchor(ack_link: str) -> str:
    safe = _html.escape(ack_link, quote=True)
    return (
        f'<a href="{safe}" style="display:inline-block;background:#2563eb;'
        f'color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600">'
        f'Acknowledge receipt</a>'
    )


def _button_html(ack_link: str) -> str:
    return f'<p style="margin:24px 0">{_button_anchor(ack_link)}</p>'


# What an org may write in the rich-text editor. Formatting only: nothing that loads a
# remote resource, runs, or restyles the message into something it isn't. Deliberately
# narrower than the editor's toolbar could produce, because the toolbar is a convenience
# and this is the actual boundary.
_ALLOWED_TAGS = {
    "p", "br", "div", "span",
    "b", "strong", "i", "em", "u", "s",
    "ul", "ol", "li",
    "h3", "h4", "blockquote", "a",
}
_ALLOWED_ATTRS = {"a": {"href", "title"}}
_ALLOWED_SCHEMES = {"http", "https", "mailto"}

_ANY_TAG = re.compile(r"<[^>]*>")
_BREAKING = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|h3|h4|blockquote)\s*>")
_BLANK_RUN = re.compile(r"\n{3,}")
_EMPTY_HREF = re.compile(r'\s*href=""')


def sanitize_body(body_html: str) -> str:
    """Reduce org-authored markup to the allowlist, then drop any placeholder sitting in a
    tag rather than in the text.

    Placeholders are text-only, and this is why. `<a href="{{notes}}">` survives
    sanitizing — a bare token reads as a relative URL, not a blocked scheme — and would
    then take whatever an asset's notes field happens to say and put it in an href. Asset
    fields are not all admin-written, so that is a link target somebody else chooses.
    Stripping tokens inside tags closes the category rather than the example.
    """
    clean = nh3.clean(
        body_html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes=_ALLOWED_SCHEMES,
        link_rel="noopener noreferrer",
    )
    stripped = _ANY_TAG.sub(lambda m: _TOKEN.sub("", m.group(0)), clean)
    # A link whose whole href was a placeholder is now a link to nowhere. Leave the words,
    # drop the empty target — in a mail client that renders as clickable text that reloads
    # the message, which reads as a broken link rather than as plain text.
    return _EMPTY_HREF.sub("", stripped)


def _to_plain_text(body_html: str) -> str:
    """Plain-text alternative for a rich-text body.

    Mail clients that show the text part get the words and the structure, not a wall with
    the line breaks removed — so the tags that mean "new line" become one before the rest
    are dropped.
    """
    text = _BREAKING.sub("\n", body_html)
    text = _html.unescape(nh3.clean(text, tags=set(), attributes={}))
    return _BLANK_RUN.sub("\n\n", text).strip()


def _substitute(text: str, ctx: dict[str, str]) -> str:
    """Replace every known `{{key}}` in one pass, leaving unknown ones alone.

    One pass, not a replace() per key: sequential replacement rewrites text it has already
    substituted, so an asset named "Dell {{org_name}}" would have had the org name spliced
    into it by a later key. Values are data and must never be re-scanned as template.
    """
    return _TOKEN.sub(lambda m: ctx.get(m.group(1), m.group(0)), text)


def render_asset_assignment(
    *,
    subject_tmpl: str | None,
    body_tmpl: str | None,
    context: dict[str, str],
    ack_link: str,
    body_format: str = "text",
) -> tuple[str, str, str]:
    """Return (subject, html, text) for the assignment email, using the org's template
    when provided or the built-in default otherwise. `context` supplies the placeholder
    values (see ASSET_PLACEHOLDERS); missing keys render as empty.

    `body_format` is "text" for a body written before the rich-text editor existed — escaped
    whole, newlines turned into breaks — or "html" for one written in it, where the markup is
    reduced to the allowlist first and only the substituted values are escaped.
    """
    subject_tmpl = subject_tmpl or DEFAULT_ASSET_SUBJECT
    body_tmpl = body_tmpl or DEFAULT_ASSET_BODY
    ctx = {key: (context.get(key) or "") for key in ASSET_PLACEHOLDERS}
    rich = body_format == "html"

    # The subject is a plain input in the editor, rich text or not, so it is never markup.
    subject = _substitute(subject_tmpl, ctx).replace("\n", " ").strip() or DEFAULT_ASSET_SUBJECT

    if rich:
        # Sanitize the author's markup, THEN substitute escaped values into it. This order
        # is the point: sanitizing afterwards would run the sanitizer over an asset's own
        # fields and quietly eat a name like "R&D <spare>"; escaping the whole document
        # instead would print the author's formatting as visible tags.
        safe_ctx = {key: _html.escape(value) for key, value in ctx.items()}
        source = sanitize_body(body_tmpl)
        # Inline anchor at the marker: the author has already placed it inside a paragraph
        # of their own, and nesting a block element there is invalid markup.
        segments = source.split(_ACK_MARKER)
        body_html = _button_anchor(ack_link).join(_substitute(s, safe_ctx) for s in segments)
        if len(segments) == 1:
            body_html += _button_html(ack_link)
        text_source = _to_plain_text(source)
    else:
        button = _button_html(ack_link)
        segments = body_tmpl.split(_ACK_MARKER)
        rendered = [
            _html.escape(_substitute(seg, ctx)).replace("\n", "<br>")
            for seg in segments
        ]
        body_html = button.join(rendered)
        if len(segments) == 1:  # author didn't place the button — append it
            body_html += button
        text_source = body_tmpl

    html = _shell("You've been assigned an asset", body_html)

    # Plain-text alternative: substitute raw values, and drop the bare link where the
    # button goes.
    text = _substitute(text_source, ctx)
    text = (text.replace(_ACK_MARKER, f"\n\nAcknowledge receipt: {ack_link}")
            if _ACK_MARKER in text else f"{text}\n\nAcknowledge receipt: {ack_link}")

    return subject, html, text
