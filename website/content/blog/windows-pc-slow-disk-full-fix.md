---
title: "Windows PC Slow or Disk Full? A Practical Clean-Up Guide for IT Teams"
description: "Fix a slow Windows 10 or 11 PC with a full C: drive: find out what's really slowing it down, clear temp files and the Windows Update cache safely, tame startup apps, and know when the answer is hardware."
date: "2026-11-05"
author: "Technomate IT-Solution"
keywords:
  - Windows PC slow
  - disk full Windows 11
  - free up disk space C drive
  - clear temp files Windows
  - Disk Cleanup
  - computer running slow fix
faq:
  - q: "How much free disk space does Windows need?"
    a: "Keep at least 10 to 15% of the C: drive free. Below that, Windows slows down, updates start failing and apps like Outlook struggle."
  - q: "Is it safe to clear temp files in Windows?"
    a: "Yes. Use Settings, System, Storage, Temporary files. Files that are in use are skipped. Check the Downloads entry before ticking it, because it deletes the user's Downloads folder."
  - q: "Can I delete the SoftwareDistribution Download folder?"
    a: "Its contents are update files Windows no longer needs once updates are installed. Use Windows Update Cleanup in Disk Cleanup or Storage settings rather than deleting files by hand, and never while an update is installing."
  - q: "When should a slow PC be upgraded instead of cleaned?"
    a: "When it still has a spinning hard drive, has 8 GB of RAM or less for a full day of Teams, browser and Office, or keeps filling a disk that is simply too small."
---

"My computer is slow" is the vaguest ticket an IT team receives, and one of the most common. Sometimes the cause is a full disk. Sometimes it is one browser tab using all the memory. Sometimes the laptop is simply too old.

Clearing temp files on every slow PC wastes time when the real cause is something else. This guide starts with finding out *what* is slow, then covers the fixes that match each cause. It is written for business Windows 10 and Windows 11 PCs.

## Step 1: find out what is actually slow

Open **Task Manager** (`Ctrl + Shift + Esc`), choose **Processes**, and sort by each column in turn:

| What you see | Likely cause | Go to |
|---|---|---|
| **Disk** at or near 100% for minutes | Low free space, an update or scan running, or an old hard drive | Steps 2 to 4, then Step 6 |
| **Memory** above 85–90% | Too many apps or browser tabs, or a memory leak | Step 5 |
| **CPU** high from one process | A stuck app, a sync client or a scan | Restart that app |
| Nothing high, but still slow | Startup apps, pending restart, or an aging device | Steps 5 and 6 |

Also check **free space on the C: drive** in File Explorer. Below roughly 10–15% free, Windows slows down, updates start failing, and apps like Outlook struggle.

## Step 2: clear temporary files

Temporary files build up in two places:

- **Per user:** `%TEMP%` (the signed-in user's temp folder).
- **System-wide:** `C:\Windows\Temp`.

The easiest safe way to clear both is Windows' own tool. Open *Settings → System → Storage → Temporary files*, review the list, and remove what you don't need. Check the **Downloads** entry carefully. It deletes the user's Downloads folder, which often holds files they still want.

Some files will be in use and can't be deleted. That's fine. Skip them.

## Step 3: clear the old Windows Update downloads

Windows keeps downloaded update files in `C:\Windows\SoftwareDistribution\Download`. After updates install, these are no longer needed, and they can take up several gigabytes.

In the same *Temporary files* screen, choose **Windows Update Cleanup** and **Delivery Optimization Files** if they appear. Or run **Disk Cleanup** (`cleanmgr`), click **Clean up system files**, and select them there.

Don't delete these while an update is installing. Check *Settings → Windows Update* first.

## Step 4: turn on Storage Sense

Storage Sense clears temporary files automatically and can empty the Recycle Bin on a schedule. Turn it on in *Settings → System → Storage → Storage Sense*. For a fleet, set it once by policy rather than on each PC.

## Step 5: memory and startup apps

If memory is the bottleneck:

- **Browsers are usually the cause.** Dozens of tabs in Chrome or Edge can use several gigabytes. Restarting the browser frees that memory, and both restore tabs on relaunch.
- **Check startup apps.** In Task Manager, open **Startup apps** and disable anything the user doesn't need the moment they sign in. Disabling only stops it starting automatically. It doesn't uninstall anything.
- **Restart the PC.** Many laptops go weeks without a real restart because they are only closed and put to sleep. A pending update restart can slow things down too.

## Step 6: know when it's hardware

Software fixes have limits. Consider an upgrade or replacement when:

- The PC still has a spinning hard drive (HDD). Moving to an SSD is the biggest single speed improvement for an older PC.
- It has 8 GB of RAM or less and the user runs Teams, a browser and Office all day.
- The disk keeps filling up because the drive is simply too small for the work.

Track device age and specs across the fleet so replacements can be planned rather than handled one ticket at a time.

## Make it routine

- **Monitor free disk space** across the fleet, and act before devices fall below 15% free.
- **Set Storage Sense by policy.**
- **Agree on a standard browser setup**, and teach users that restarting the browser is a fix, not a failure.
- **Record which step fixed each ticket.** Patterns appear quickly, like one model with a small SSD or one team with a heavy sync tool.

For update failures caused by low disk space, see [how to reset Windows Update components](/blog/reset-windows-update-components/).

## Where SAVIO fits

[SAVIO](/savio/) is the AI System Administrator we build for Windows fleets. For slow PCs:

- **Evidence first.** The SAVIO agent reports each device's CPU, memory and disk use, so a "slow PC" ticket starts with data instead of guesses.
- **Clean-up is automatic.** SAVIO can clear the user's temp files, and do a deeper clean of system temp, prefetch, the Windows Update download cache and error reports. These folders rebuild themselves.
- **Browser fixes are automatic.** SAVIO can restart Chrome or Edge, or clear the browser cache without touching history, passwords, bookmarks or cookies.
- **Every action is audited**, so devices that keep running out of space stand out for replacement.

If "my computer is slow" tickets keep coming back, [book a 30-minute fleet assessment](/contact/). We will look at your Windows devices and show you what can safely be automated.
