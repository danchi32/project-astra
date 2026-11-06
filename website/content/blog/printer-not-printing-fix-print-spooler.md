---
title: "Printer Not Printing on Windows? How to Fix a Stuck Print Spooler"
description: "Print jobs stuck in the queue or the printer showing offline on office Windows PCs? A step-by-step fix: restart the Print Spooler, clear stuck jobs safely, and find the driver behind a spooler that keeps stopping."
date: "2026-10-31"
author: "Technomate IT-Solution"
keywords:
  - printer not printing
  - print spooler not working
  - clear print queue Windows
  - restart print spooler
  - print spooler keeps stopping
  - printer offline Windows 11
faq:
  - q: "How do I clear a stuck print queue in Windows?"
    a: "Stop the Print Spooler, delete the files in `C:\\Windows\\System32\\spool\\PRINTERS`, then start the spooler again. This removes every pending job on that PC, so users may need to print again."
  - q: "Why does the Print Spooler keep stopping?"
    a: "Usually a faulty or outdated printer driver. Check Event Viewer under PrintService for the driver named in the error, remove old printers, and install the manufacturer's current driver."
  - q: "Why does Windows say my printer is offline when it is on?"
    a: "The printer's IP address may have changed, 'Use Printer Offline' may be ticked, or the PC may be on a network that can't see the printer, such as a VPN or guest Wi-Fi. Give network printers a reserved IP address."
---

"The printer isn't working" is one of the most common tickets in any office. Usually the printer is fine. The problem is on the PC: a job is stuck in the queue and everything behind it waits.

This guide covers the fix in the order an IT team should try it. It is written for business Windows 10 and Windows 11 PCs. The commands need an **elevated** Command Prompt (run as administrator).

## First, a 60-second check

Before touching the spooler, rule out the obvious:

- **Is the printer on, online and not out of paper or toner?** Check the printer's own display.
- **Can other people print to it?** If nobody can, the problem is the printer or the network, not this PC.
- **Is the right printer selected?** After a move between offices or a new dock, Windows may default to a printer at the old location.
- **Does the queue show a job with an error?** Open *Settings → Bluetooth & devices → Printers & scanners*, pick the printer and open the print queue.

If only this PC is affected and there is a job stuck in the queue, the Print Spooler is the next step.

## What the Print Spooler does

The Print Spooler is the Windows service that takes every print job, holds it on disk, and hands it to the printer driver. If one job gets stuck, because it is corrupt, too large or was sent to a printer that went away, the jobs behind it stop too.

Cancelling the job from the queue window often does nothing. The job stays at "Deleting" forever because the spooler itself is stuck.

## Fix 1: restart the Print Spooler

This clears most stuck queues and takes seconds.

```
net stop spooler
net start spooler
```

Or use the Services console: press `Win + R`, type `services.msc`, find **Print Spooler**, right-click and choose **Restart**.

Try printing a test page. If the stuck job is still there, go to Fix 2.

## Fix 2: clear the stuck jobs

Restarting does not always remove a corrupt job, because the spooler reloads it from disk. To remove it, stop the spooler, delete the spooled job files, then start it again:

```
net stop spooler
del /Q /F %systemroot%\System32\spool\PRINTERS\*
net start spooler
```

**This deletes every pending job on that PC, not just the stuck one.** Tell the user they may need to print again. Only delete the contents of the `PRINTERS` folder. Do not touch the `drivers` folder next to it.

## Fix 3: the spooler keeps stopping

If the Print Spooler stops again minutes after you start it, or every time someone prints, the usual cause is a faulty or outdated printer driver.

1. Open **Event Viewer** and go to *Windows Logs → System*, and also to *Applications and Services Logs → Microsoft → Windows → PrintService → Admin*. Look for errors at the time the spooler stopped. They often name the driver or DLL involved.
2. Remove printers that are no longer in use, especially old ones left over from previous offices.
3. Install the current driver from the printer manufacturer, ideally the same version across the fleet.
4. If a single printer keeps causing it, remove and re-add that printer with the fresh driver.

**Don't weaken print security to make a driver install work.** Since the PrintNightmare vulnerabilities, Windows restricts who can install printer drivers. That is deliberate. Deploy drivers centrally through your management tooling or an administrator rather than switching those protections off.

## Fix 4: the printer shows "offline"

If the queue is clear but Windows still says the printer is offline:

- Check the printer's IP address hasn't changed. A printer that gets its address from DHCP can move, and the PC keeps looking at the old address. Give network printers a reserved or static IP.
- Make sure *Use Printer Offline* is not ticked in the print queue's **Printer** menu.
- Check the PC is on the right network. A VPN or a guest Wi-Fi network often cannot see office printers.

## Reduce printer tickets across the office

Printer tickets come back when the same causes stay in place. A few habits cut them down:

- One approved driver per printer model, deployed the same way everywhere.
- Reserved IP addresses for every network printer.
- A clean-up of old printer entries on PCs once a quarter.
- Track which printer and which PCs generate the tickets. A single bad driver often explains most of them.

## Where SAVIO fits

[SAVIO](/savio/) is the AI System Administrator we build for Windows fleets. For printing:

- **Restarting the Print Spooler is automatic.** It is one of the allowlisted Windows services SAVIO can restart on its own, and it checks afterwards that the service is running again.
- **Adding a network printer is automatic** too, so a user who moved desks can get the right printer without waiting on a ticket.
- **Evidence before action.** SAVIO reads the device's services and recent system events before proposing a fix, so a spooler that keeps crashing points to the driver rather than restarting it again and again.
- **Everything is audited**, so you can see which PCs and printers keep coming back.

If printer and other repetitive tickets are taking up your team's day, [book a 30-minute fleet assessment](/contact/) and we will show you what can safely be automated on your Windows devices.
