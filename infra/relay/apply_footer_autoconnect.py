#!/usr/bin/env python3
"""Inject the ASTRA desktop auto-connect shim into the MeshCentral relay config.

WHY THIS EXISTS
---------------
The ASTRA portal embeds a MeshCentral desktop viewer in an iframe. The viewer link
carries the target device as `?gotonode=<bare node id>&viewmode=11`. MeshCentral is
*supposed* to select that device and open its Desktop tab on load — but on this relay it
never does, for a reason that is baked into MeshCentral's own web app:

    function gotoStartViewPage() {
        var xviewmode = parseInt('11');
        if (xxcurrentView != -1) return;          // <-- the guard
        ... else if (args.gotonode != null) {
            if (getNodeFromId('node//'+args.gotonode) == null) return;  // node not loaded yet
            gotoDevice('node//'+args.gotonode, xviewmode);
        }
    }

`viewmode=11` sets the current view to the (empty) desktop tab *before* the device list
arrives over the websocket. By the time the device is loaded, `xxcurrentView != -1`, so
the guard returns early and the `gotonode` branch never runs. Result: the iframe shows a
Desktop tab with the Connect button greyed out, no device selected, and — crucially — no
consent prompt ever reaches the end user. Verified empirically: `gotonode` selects nothing
here, with or without `viewmode`, however long you wait, even though the node is online and
`getNodeFromId('node//...')` resolves it fine.

The public web-app functions work perfectly when called directly:
    gotoDevice('node//<id>', 11, true)   -> selects the device, opens Desktop, enables Connect
    document.getElementById('connectbutton1').click()  -> connects, which raises the
                                                          consent prompt on the endpoint.

So this shim drives exactly those two calls once the device list has loaded. It is injected
through MeshCentral's supported `domains."".footer` config field, which is emitted raw
(`{{{footer}}}`, triple-brace) into default.handlebars, so an inline <script> there runs on
every app page load. The shim is a no-op unless the URL carries `gotonode`, so a normal
operator opening the console is completely unaffected.

This is deliberately a relay-side change and NOT ASTRA application code: the defect is in
MeshCentral's page, the relay is not in CI, and the ASTRA viewer URL already carries
everything the shim needs (no backend change). Kept here, version-controlled and reversible
(every run writes a timestamped .bak), so the customization is not a mystery living only on
a VM. If MeshCentral is upgraded and fixes gotonode, delete the footer and this shim becomes
dead weight, not a breakage — gotoDevice on an already-selected node is idempotent.

USAGE (run on the relay VM, needs sudo):
    sudo python3 apply_footer_autoconnect.py            # inject / update
    sudo python3 apply_footer_autoconnect.py --remove   # revert to no footer
then restart:  sudo systemctl restart meshcentral
"""
import json
import shutil
import sys
import time

CONFIG = "/opt/meshcentral/meshcentral-data/config.json"

# The shim. Minified onto one line so it lives cleanly as a JSON string. Guard clause first:
# nothing happens for URLs without gotonode, i.e. ordinary operator logins.
FOOTER = (
    "<script>/*ASTRA auto-connect shim -- see infra/relay/apply_footer_autoconnect.py. "
    "MeshCentral's built-in gotonode is dead on cold load (xxcurrentView guard), so drive "
    "the public gotoDevice()+Connect API once the device list has loaded. No-op unless the "
    "URL carries gotonode, so normal console logins are unaffected.*/"
    "(function(){try{"
    "var m=/[?&]gotonode=([^&]+)/.exec(window.location.search);if(!m)return;"
    "var nid='node//'+decodeURIComponent(m[1]);"
    "var d1=Date.now()+45000;"
    "var t1=setInterval(function(){"
    "if(Date.now()>d1){clearInterval(t1);return;}"
    "if(typeof window.getNodeFromId!=='function'||typeof window.gotoDevice!=='function')return;"
    "if(window.getNodeFromId(nid)==null)return;"          # device not in the list yet -> wait
    "clearInterval(t1);"
    "try{window.gotoDevice(nid,11,true);}catch(e){}"       # select device, open Desktop tab
    "var d2=Date.now()+30000;"
    "var t2=setInterval(function(){"
    "if(Date.now()>d2){clearInterval(t2);return;}"
    "var b=document.getElementById('connectbutton1');"
    "if(b&&!b.disabled){clearInterval(t2);try{b.click();}catch(e){}}"  # Connect -> consent prompt
    "},300);},400);}catch(e){}})();</script>"
)


def main() -> int:
    remove = "--remove" in sys.argv
    with open(CONFIG) as fh:
        cfg = json.load(fh)

    bak = f"{CONFIG}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(CONFIG, bak)

    domain = cfg.setdefault("domains", {}).setdefault("", {})
    if remove:
        domain.pop("footer", None)
        action = "removed footer"
    else:
        domain["footer"] = FOOTER
        action = f"set footer ({len(FOOTER)} chars)"

    with open(CONFIG, "w") as fh:
        json.dump(cfg, fh, indent=2)
    # Re-read to prove we wrote valid JSON before anyone restarts the service on it.
    with open(CONFIG) as fh:
        json.load(fh)

    print(f"OK: {action}")
    print(f"backup: {bak}")
    print("now run: sudo systemctl restart meshcentral")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
