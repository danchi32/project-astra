"""Seed the global knowledge base with starter runbooks.

    python scripts/seed_knowledge.py --dry-run    # what would be written
    python scripts/seed_knowledge.py              # write them

Global, not per-organization: these are shared with every customer, so a new org gets a
useful assistant on day one instead of one that searches an empty knowledge base.

Every article below is tied to a remediation ASTRA can actually perform, and names the
`action_id`. That is the whole point — an article describing a fix the platform cannot run
teaches the assistant to promise something it then has to walk back. The set covers 20 of
the 22 registered actions; the two it leaves out are `registry_fix` (its fixes are
per-registry-key and belong to whoever authored them) and `enable_local_account` (the
reversal of an offboarding, not a symptom anyone reports).

Each one also states the approval tier, because "I can do this now" and "I need your
admin to approve this" are different sentences and the user should hear the right one.

Idempotent: an article whose title already exists is skipped, so this is safe to re-run
after adding more.
"""
import argparse
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import KnowledgeArticle  # noqa: E402
from app.services.ai.knowledge import KnowledgeBaseService  # noqa: E402


ARTICLES: list[tuple[str, str]] = [
    (
        "Outlook won't open or is stuck",
        "Symptoms: Outlook does not launch, hangs on 'Processing', shows a white window, or "
        "stops sending and receiving.\n\n"
        "1. Restart Outlook (action_id: restart_outlook, runs automatically). This clears "
        "most hangs — a background Outlook process is usually still holding the profile.\n"
        "2. If it fails again straight after restarting, the install is damaged rather than "
        "stuck. Repair Office (action_id: office_repair). This needs IT approval and closes "
        "every Office app, so tell the user to save their work first.\n\n"
        "Do not repair Office on the first failure. A repair takes several minutes and a "
        "restart fixes the large majority of these."
    ),
    (
        "Microsoft Teams won't load, sign in, or shows a blank window",
        "Symptoms: Teams sits on the splash screen, shows a blank white window, will not "
        "connect, or the microphone and camera are missing from a call.\n\n"
        "1. Restart Teams (action_id: restart_teams, runs automatically).\n"
        "2. If Teams loads but audio or video is missing, that is a Windows privacy setting "
        "and not a Teams fault — the user has to allow microphone and camera access under "
        "Settings > Privacy & security. ASTRA cannot change that for them.\n"
        "3. If Teams still will not connect after a restart, check whether the device has a "
        "working connection at all before assuming Teams is at fault."
    ),
    (
        "Wi-Fi keeps dropping or there is no internet connection",
        "Symptoms: the connection drops every few minutes, Wi-Fi shows connected but nothing "
        "loads, or the network icon shows no internet.\n\n"
        "1. Restart the network adapter (action_id: restart_network_adapter, runs "
        "automatically). This recovers a dropped or half-connected adapter.\n"
        "2. If pages still do not load but the adapter is up, flush the DNS cache "
        "(action_id: flush_dns, runs automatically) — a stale or poisoned cache looks "
        "exactly like a dead connection.\n"
        "3. Only if both fail, reset the network stack (action_id: network_reset). This "
        "needs IT approval, drops every connection on the device, and usually wants a "
        "restart afterwards — so it is the last step, not the first.\n\n"
        "If several devices in the same office report this at once it is the access point "
        "or the ISP, not the endpoints. Check the fleet view before fixing them one by one."
    ),
    (
        "Websites will not load or a site says it cannot be found",
        "Symptoms: a specific site fails while others work, the browser says the server "
        "cannot be found, or an internal site stopped resolving after a network change.\n\n"
        "1. Flush the DNS cache (action_id: flush_dns, runs automatically). A stale entry "
        "after a DNS change is the usual cause.\n"
        "2. If the page loads but looks broken or shows old content, clear the browser "
        "cache (action_id: clear_browser_cache, runs automatically). This clears the HTTP "
        "cache only — history, passwords, bookmarks and cookies are untouched, so the user "
        "will not be signed out of anything."
    ),
    (
        "The disk is full or Windows warns about low disk space",
        "Symptoms: a low disk space warning, Windows updates failing to download, Office "
        "refusing to save, or the device slowing to a crawl.\n\n"
        "1. Clear temporary files (action_id: clear_temp, runs automatically). Cleans the "
        "signed-in user's temp folder.\n"
        "2. If that does not free enough, deep clean the system temp (action_id: "
        "clear_system_temp, runs automatically). This clears C:\\Windows\\Temp, Prefetch, "
        "the Windows Update download cache and Windows Error Reports. All of it rebuilds "
        "itself; nothing the user owns is deleted.\n\n"
        "Neither step touches documents, downloads or the recycle bin. If the disk is still "
        "full after both, the space is in real user data and a person has to decide what "
        "goes — ASTRA will not delete it."
    ),
    (
        "The computer is very slow",
        "Symptoms: everything takes a long time, the fan is loud, applications take many "
        "seconds to open.\n\n"
        "Check the evidence before acting — 'slow' has several different causes and the "
        "wrong fix wastes the user's time:\n\n"
        "1. Disk nearly full: deep clean the system temp (action_id: clear_system_temp).\n"
        "2. One application eating memory — usually a browser with many tabs open for days: "
        "restart it (action_id: restart_chrome or restart_edge). Both restore the previous "
        "tabs on relaunch, so the user loses nothing.\n"
        "3. Pending Windows updates: these keep a device busy in the background. See the "
        "Windows updates article.\n\n"
        "If CPU and memory are both normal and the disk has space, the device is not slow "
        "in a way ASTRA can fix remotely and it needs a hardware check."
    ),
    (
        "The taskbar, Start menu or desktop is frozen",
        "Symptoms: the taskbar does not respond, Start does not open, icons are missing, or "
        "the desktop is black but the mouse still moves.\n\n"
        "Restart Windows Explorer (action_id: restart_explorer, runs automatically). This "
        "restarts the Windows shell only — open applications and unsaved work are not "
        "affected, though the screen will flicker and the taskbar will disappear for a "
        "second. Tell the user to expect that so they do not think it crashed.\n\n"
        "This is almost always the right first step and it is far quicker than a reboot."
    ),
    (
        "Printing does not work or the print queue is stuck",
        "Symptoms: jobs sit in the queue and never print, the printer shows offline, or "
        "nothing happens when the user prints.\n\n"
        "1. Restart the Print Spooler service (action_id: restart_service, service_name: "
        "Spooler — runs automatically). A stuck spooler is the most common cause and this "
        "clears the jammed queue.\n"
        "2. Warn the user that queued jobs are cleared, so anything waiting has to be sent "
        "again.\n"
        "3. If the printer still shows offline after that, it is the printer or the network "
        "path to it, not the PC — someone has to check the device itself."
    ),
    (
        "Chrome or Edge is slow, hanging, or will not open",
        "Symptoms: the browser stops responding, uses a lot of memory, tabs crash, or it "
        "will not start at all.\n\n"
        "1. Restart the browser (action_id: restart_chrome or restart_edge, runs "
        "automatically). Both restore the previously open tabs, so a user with thirty tabs "
        "open does not lose them.\n"
        "2. If pages load slowly or show stale content rather than hanging, clear the "
        "browser cache instead (action_id: clear_browser_cache). Signed-in sessions, "
        "bookmarks and saved passwords are not affected."
    ),
    (
        "Zoom will not start or is stuck in a meeting",
        "Symptoms: Zoom does not open, sits on a black window, or thinks it is still in a "
        "meeting that has ended.\n\n"
        "Restart Zoom (action_id: restart_zoom, runs automatically). A Zoom process left "
        "behind after a meeting is the usual cause of both.\n\n"
        "If audio or video is missing once Zoom is open, that is a Windows privacy setting "
        "for the microphone and camera and the user has to allow it themselves."
    ),
    (
        "An application is not responding or will not open",
        "Symptoms: a program shows 'Not responding', its window will not come to the front, "
        "or clicking its icon does nothing.\n\n"
        "Restart the application (action_id: restart_application, process_name: the "
        "executable — runs automatically). This closes it and opens it again.\n\n"
        "Only applications on the safe allowlist can be restarted this way, which is "
        "deliberate: force-closing arbitrary processes on someone's machine can lose their "
        "work. Warn the user that unsaved work in that application will be lost."
    ),
    (
        "Windows updates are pending or keep failing",
        "Symptoms: updates listed as pending for weeks, an update that downloads and fails "
        "repeatedly, or a device flagged as out of compliance for patching.\n\n"
        "1. Check what the state actually is first. 'Pending restart' means the update is "
        "already installed and the device just needs rebooting — installing again does "
        "nothing. 'Failed' is a different problem entirely.\n"
        "2. For genuinely pending updates: install them (action_id: "
        "windows_update_install). Needs IT approval. It never reboots on its own — it "
        "reports when a restart is required and the user chooses when.\n"
        "3. For an update that keeps failing, the component store is usually damaged. Reset "
        "the Windows Update components (action_id: reset_windows_update_components). Admin "
        "approval only, and it is slow, so confirm the update has genuinely failed more "
        "than once first.\n\n"
        "If updates fail across many devices at the same time, that is a Microsoft-side or "
        "network problem — check the fleet view before touching them individually."
    ),
    (
        "Windows Search is not returning results",
        "Symptoms: the Start menu search finds nothing, Explorer search returns no results, "
        "or Outlook search misses recent mail.\n\n"
        "Restart the Windows Search service (action_id: restart_service, service_name: "
        "WSearch — runs automatically).\n\n"
        "Tell the user that the index rebuilds afterwards and results may be incomplete for "
        "a while — on a machine with a lot of files that can take a few hours. Otherwise "
        "they report it as broken again an hour later."
    ),
    (
        "Too much email from one sender",
        "Symptoms: a user is being flooded by a newsletter, an automated alert, or a "
        "mailing list, and wants it out of the inbox without losing it.\n\n"
        "Create an Outlook inbox rule (action_id: create_outlook_rule, from_address: the "
        "sender, folder_name: where it should go — runs automatically). Incoming mail from "
        "that address moves to the folder, which is created if it does not exist.\n\n"
        "This affects desktop Outlook only, and it applies to new mail — messages already "
        "in the inbox stay where they are. It is reversible: the user can delete the rule "
        "in Outlook themselves. Confirm the exact address with them first; a rule on the "
        "wrong sender hides mail they needed."
    ),
    (
        "A driver is out of date or hardware is not working",
        "Symptoms: no sound, a display stuck at the wrong resolution, a webcam or "
        "touchpad that stopped working, or a device showing an error in Device Manager.\n\n"
        "Update the driver (action_id: driver_update, device_class: the hardware class). "
        "Needs IT approval.\n\n"
        "Confirm which hardware is affected before requesting this. A driver update can "
        "require a restart and, occasionally, makes things worse — so it is worth checking "
        "the device was working before a recent change rather than updating on a guess."
    ),
    (
        "An employee is leaving and their access must be cut off",
        "Symptoms: an offboarding, a suspension, or a laptop that has to be locked now.\n\n"
        "Disable the local Windows account (action_id: disable_local_account, username: "
        "the account). Admin approval only. It signs the user out immediately and stops "
        "them signing back in.\n\n"
        "What it does not do: it does not change the password, delete anything, or touch "
        "their files — and it is fully reversible with enable_local_account if the "
        "offboarding is cancelled.\n\n"
        "It applies to LOCAL Windows accounts only. Domain and Entra accounts are managed "
        "in Active Directory or Intune, and disabling a local account does not stop someone "
        "signing in with a domain account. Say that plainly rather than letting anyone "
        "believe access is fully revoked when it is not."
    ),
]


async def main(dry_run: bool) -> int:
    async with SessionLocal() as session:
        existing = set((await session.execute(select(KnowledgeArticle.title))).scalars().all())

    new = [(t, c) for t, c in ARTICLES if t not in existing]
    print(f"Starter articles defined: {len(ARTICLES)}")
    print(f"Already present:          {len(ARTICLES) - len(new)}")
    print(f"To create:                {len(new)}")

    if dry_run:
        for title, _ in new:
            print(f"  + {title}")
        print("\nDry run — nothing was written.")
        return 0

    if not new:
        print("Nothing to do.")
        return 0

    async with SessionLocal() as session:
        service = KnowledgeBaseService(session)
        for title, content in new:
            # create_global also generates the query aliases and the embedding, which is
            # what makes these findable by the words a user types rather than the words we
            # happened to title them with.
            await service.create_global(title=title, content=content)
            print(f"  created: {title}", flush=True)

    print(f"\nCreated {len(new)} global article(s).")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="list what would be created")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run)))
