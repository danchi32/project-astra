---
title: "Outlook Not Responding? A Step-by-Step Fix for Business Windows PCs"
description: "Outlook freezing, stuck on 'Processing' or showing 'Not Responding'? Fixes in the right order for Microsoft 365 users: restart cleanly, safe mode and add-ins, Office Quick and Online Repair, and rebuilding the OST file."
date: "2026-11-05"
author: "Technomate IT-Solution"
keywords:
  - Outlook not responding
  - Outlook keeps freezing
  - Outlook safe mode
  - repair Microsoft Office
  - rebuild OST file
  - Outlook stuck on processing
faq:
  - q: "How do I start Outlook in safe mode?"
    a: "Press Win + R, type `outlook.exe /safe` and press Enter. Outlook starts without add-ins, which tells you whether an add-in is causing the freezes."
  - q: "Is it safe to delete the Outlook OST file?"
    a: "For Microsoft 365 and Exchange mailboxes, yes: the OST is a local copy and Outlook downloads the mailbox again. Rename it rather than deleting it. Never do this with a PST file, which may be the only copy of some mail."
  - q: "What is the difference between Quick Repair and Online Repair?"
    a: "Quick Repair is fast and works offline. Online Repair reinstalls Office completely, takes longer and needs an internet connection. Try Quick Repair first; both close every Office app."
---

Outlook is the application people notice first when it breaks. When it freezes, nobody can read or send mail, and the ticket arrives marked urgent.

Most Outlook hangs have one of a few causes: a stuck process, a bad add-in, a damaged Office installation, or a damaged local mailbox cache. This guide works through them from the quickest fix to the slowest. It is written for desktop Outlook on business Windows 10 and Windows 11 PCs connected to Microsoft 365 or Exchange.

## Step 0: is it Outlook, or the mailbox?

Ask the user to sign in to [Outlook on the web](https://outlook.office.com) in a browser.

- If the web version is also slow or missing mail, the problem is the mailbox or the service, not the PC. Check the Microsoft 365 service health page in the admin centre.
- If the web version works fine, the problem is on this PC. Carry on.

## Step 1: close Outlook properly and reopen it

"Not Responding" often means Outlook is waiting on something, like a large attachment, a sync or a slow add-in. Give it a minute first. If it stays frozen:

1. Open **Task Manager** (`Ctrl + Shift + Esc`).
2. Find **Microsoft Outlook**, select it and choose **End task**.
3. Check the **Details** tab for a leftover `OUTLOOK.EXE` and end that too.
4. Start Outlook again.

A clean restart fixes most one-off hangs. If Outlook freezes again within minutes, go to Step 2.

## Step 2: start in safe mode to test add-ins

Add-ins (for CRM, PDF tools, meeting plugins and similar) are the most common cause of Outlook that freezes repeatedly. Safe mode starts Outlook without them:

1. Press `Win + R`.
2. Type `outlook.exe /safe` and press Enter.

If Outlook runs smoothly in safe mode, an add-in is the cause:

1. Close safe mode and start Outlook normally.
2. Go to *File → Options → Add-ins*, choose **COM Add-ins** next to *Manage*, and click **Go**.
3. Untick all add-ins, restart Outlook, then turn them back on one at a time until the freeze returns.

Remove or update the add-in that causes it. If the same add-in breaks Outlook on several PCs, deal with it once, centrally.

## Step 3: repair Office

If safe mode freezes too, the Office installation may be damaged. Windows has a built-in repair:

1. Close all Office apps. The repair closes them anyway and **unsaved work in Word or Excel is lost**.
2. Open *Settings → Apps → Installed apps*, find **Microsoft 365** (or Microsoft Office), choose **Modify**.
3. Pick **Quick Repair** first. It is fast and works offline.
4. If the problem continues, run **Online Repair**. It reinstalls Office completely, takes longer and needs an internet connection.

The repair asks for administrator permission, so plan it with the user rather than starting it in the middle of their work.

## Step 4: rebuild the local mailbox cache (OST)

With Microsoft 365 and Exchange, Outlook keeps a local copy of the mailbox in an `.ost` file. If that file is damaged, Outlook can freeze while loading or syncing. The copy on the server is the real mailbox, so the local file can be rebuilt:

1. Close Outlook.
2. Open *Control Panel → Mail (Microsoft Outlook) → Data Files* to see where the `.ost` file is stored.
3. Rename the file, for example add `.old` to the end.
4. Start Outlook. It downloads the mailbox again and creates a new file.

**Only do this for `.ost` files.** A `.pst` file is not a copy. It may be the only place some mail exists. For a damaged PST, use Microsoft's Inbox Repair Tool (`SCANPST.EXE`) instead, and take a backup first.

A full re-download can take hours on a large mailbox. Do it at the end of the day where possible.

## Step 5: create a new Outlook profile

If nothing above helps, the Outlook profile itself may be damaged. In *Control Panel → Mail → Show Profiles*, add a new profile, set it as the one to always use, and sign in again. Keep the old profile until the new one is confirmed working.

## Keep Outlook tickets down

- **Agree on a short list of approved add-ins.** Most repeat freezes come from add-ins nobody remembers installing.
- **Keep Office updated** on the same channel across the company.
- **Watch disk space.** A nearly full system drive slows Outlook and can break OST syncing.
- **Record which step fixed each ticket.** If the same PCs keep needing a repair or a rebuild, look for a shared cause.

## Where SAVIO fits

[SAVIO](/savio/) is the AI System Administrator we build for Windows fleets. For Outlook:

- **Restarting Outlook is automatic.** SAVIO can close and reopen a frozen Outlook on its own.
- **Repairing Office needs approval.** Because the repair closes every Office app, IT approves it and the user clicks through the repair on their PC.
- **Simple requests are handled too.** SAVIO can create an Outlook inbox rule, such as moving mail from one sender into a folder, without a ticket.
- **Every action is audited**, so repeat problems are easy to spot.

If Outlook and other repetitive tickets are using up your team's time, [book a 30-minute fleet assessment](/contact/). We will show you what can safely be automated on your Windows devices.
