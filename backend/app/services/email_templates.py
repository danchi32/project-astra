"""Rendering for the org-customizable asset-assignment email.

The org authors a **plain-text** subject and body with `{{placeholders}}`. We substitute
the values, HTML-escape everything (so an asset name can never inject markup), wrap it in
the branded shell, and add the "Acknowledge receipt" button — positioned at
`{{acknowledge_button}}` if the author placed it, otherwise appended.
"""
from __future__ import annotations

import html as _html

# Placeholders offered to the org (shown in the editor). Keep in sync with the UI.
ASSET_PLACEHOLDERS = ["employee_name", "asset_name", "asset_tag", "org_name"]
_ACK_MARKER = "{{acknowledge_button}}"

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


def _button_html(ack_link: str) -> str:
    safe = _html.escape(ack_link, quote=True)
    return (
        f'<p style="margin:24px 0"><a href="{safe}" style="display:inline-block;background:#2563eb;'
        f'color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600">'
        f'Acknowledge receipt</a></p>'
    )


def _substitute(text: str, ctx: dict[str, str]) -> str:
    for key, value in ctx.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def render_asset_assignment(
    *,
    subject_tmpl: str | None,
    body_tmpl: str | None,
    employee_name: str,
    asset_name: str,
    asset_tag: str | None,
    org_name: str,
    ack_link: str,
) -> tuple[str, str, str]:
    """Return (subject, html, text) for the assignment email, using the org's template
    when provided or the built-in default otherwise."""
    subject_tmpl = subject_tmpl or DEFAULT_ASSET_SUBJECT
    body_tmpl = body_tmpl or DEFAULT_ASSET_BODY
    ctx = {
        "employee_name": employee_name,
        "asset_name": asset_name,
        "asset_tag": asset_tag or "",
        "org_name": org_name,
    }

    subject = _substitute(subject_tmpl, ctx).replace("\n", " ").strip() or DEFAULT_ASSET_SUBJECT

    # HTML body: escape each segment (with values already substituted), turn newlines into
    # line breaks, then place the button at the marker — or append it if absent.
    button = _button_html(ack_link)
    segments = body_tmpl.split(_ACK_MARKER)
    rendered = [
        _html.escape(_substitute(seg, ctx)).replace("\n", "<br>")
        for seg in segments
    ]
    body_html = button.join(rendered)
    if len(segments) == 1:  # author didn't place the button — append it
        body_html += button
    html = _shell("You've been assigned an asset", body_html)

    # Plain-text alternative: substitute, and drop the raw link where the button goes.
    text = _substitute(body_tmpl, ctx)
    text = (text.replace(_ACK_MARKER, f"\n\nAcknowledge receipt: {ack_link}")
            if _ACK_MARKER in text else f"{text}\n\nAcknowledge receipt: {ack_link}")

    return subject, html, text
