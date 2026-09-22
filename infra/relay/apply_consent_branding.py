#!/usr/bin/env python3
"""Brand the endpoint consent prompt, and give it a slot for the requester + reason.

The consent dialog the end user sees when a technician connects is drawn by the MeshAgent
on the device. Two things about it are wrong out of the box for ASTRA:

1. Its title bar reads "MeshCentral". The agent hardcodes that
   (agents/meshcore.js: `var consentTitle = 'MeshCentral'`), but immediately overrides it
   from `soptions.consentTitle`, which the server fills from `domains."".consentMessages.title`.
   So setting that key relabels the dialog "ASTRA Remote Support" with no agent change.

2. Its body was a fixed sentence with no room for WHO is connecting or WHY. The agent builds
   the body from a template with two slots — `{0}` = the connecting account's realname,
   `{1}` = its username (meshcore.js: `desktopConsent.replace('{0}', realname)`). The server
   fills the template from `consentMessages.desktop`. ASTRA sets the scoped relay user's
   realname to "<technician> (reason: <reason>)" per session (see the backend's request path),
   so a `{0}` in this template surfaces exactly who asked and why, on the person's own screen,
   before they allow anything — which is the whole point of a consent prompt.

Relay-side because it is the agent's dialog and the relay's config; the per-session realname
that fills `{0}` is set by the backend over the control channel. Version-controlled and
reversible (timestamped .bak each run) so the relay's customisation is not a mystery on a VM.

USAGE (on the relay VM, needs sudo):
    sudo python3 apply_consent_branding.py            # apply
    sudo python3 apply_consent_branding.py --show     # print current values
then restart:  sudo systemctl restart meshcentral
"""
import json
import shutil
import sys
import time

CONFIG = "/opt/meshcentral/meshcentral-data/config.json"

TITLE = "ASTRA Remote Support"
# {0} is the connecting account's realname, which the backend sets per session to
# "<technician> (reason: <reason>)". Keep it one line — the native dialog does not wrap
# reliably — and phrase it so the substituted realname reads as the sentence's subject.
DESKTOP = ("{0} is requesting to remotely view and control your screen for IT support. "
           "Do you allow this session?")


def main() -> int:
    with open(CONFIG) as fh:
        cfg = json.load(fh)
    domain = cfg.setdefault("domains", {}).setdefault("", {})
    # MeshCentral lower-cases config keys internally, so an existing "consentMessages"
    # and a new "consentmessages" would merge to the same object — but keep one spelling
    # in the file. Reuse whichever key is already present.
    key = "consentMessages" if "consentMessages" in domain else "consentmessages"
    msgs = domain.setdefault(key, {})

    if "--show" in sys.argv:
        print(json.dumps(msgs, indent=2))
        return 0

    bak = f"{CONFIG}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(CONFIG, bak)
    msgs["title"] = TITLE
    msgs["desktop"] = DESKTOP

    with open(CONFIG, "w") as fh:
        json.dump(cfg, fh, indent=2)
    with open(CONFIG) as fh:
        json.load(fh)  # prove valid JSON before anyone restarts on it

    print(f"OK: set {key}.title and {key}.desktop")
    print(f"backup: {bak}")
    print("now run: sudo systemctl restart meshcentral")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
