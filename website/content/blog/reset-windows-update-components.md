---
title: "Windows Update Stuck or Failing? How to Reset Windows Update Components"
description: "Step-by-step fix for Windows updates that fail, download forever or show errors like 0x80070002: what to check first, how to reset SoftwareDistribution and catroot2 safely, and what to do if it still fails."
date: "2026-10-31"
author: "Technomate IT-Solution"
keywords:
  - reset Windows Update components
  - Windows Update stuck
  - Windows Update failed
  - SoftwareDistribution folder
  - catroot2
  - Windows Update error 0x80070002
faq:
  - q: "Is it safe to delete the SoftwareDistribution folder?"
    a: "Renaming it is safer than deleting it. Windows rebuilds the folder on the next update check, and the renamed copy stays available if you need to restore it. Stop the Windows Update, Cryptographic, BITS and Windows Installer services first."
  - q: "Will resetting Windows Update components delete my files?"
    a: "No. It only rebuilds Windows Update's own caches. Downloads in progress are discarded and the update history list in Settings may look empty afterwards, but personal files and installed apps are untouched."
  - q: "What should I try before resetting Windows Update?"
    a: "Restart the PC if a restart is pending, free up disk space, and check the PC can reach Microsoft through any proxy or VPN. A reset only helps when the update cache itself is corrupted."
  - q: "What if updates still fail after the reset?"
    a: "Run `DISM /Online /Cleanup-Image /RestoreHealth` and then `sfc /scannow` from an elevated Command Prompt, restart, and try again. If the same device keeps failing, consider a repair upgrade or a rebuild."
---

An update sits at 0% for an hour. Or it downloads, installs, fails, and tries again the next night. Or Windows shows an error code and nothing else.

Resetting the Windows Update components fixes a large share of these cases. But it is a heavy step, and running it first wastes time on problems it cannot fix. This guide works through the cheap checks first and then the reset itself, step by step.

It is written for IT teams looking after business Windows 10 and Windows 11 PCs. Every command needs an **elevated** Command Prompt (run as administrator).

## Before you reset anything: four quick checks

Most stuck updates have a simpler cause. Check these first. Each takes a minute.

1. **Is the update actually stuck, or waiting on a restart?** An update that says "pending restart" is already installed. Installing it again does nothing. Restart the PC and check again.
2. **Is there enough free disk space?** Feature updates need many gigabytes free on the system drive. Error `0x80070070` means the disk is full. [Clear temporary files](/blog/windows-pc-slow-disk-full-fix/) before anything else.
3. **Can the PC reach Microsoft?** Proxies, VPNs and firewall rules often block update downloads. `0x8024402C` usually points to a connection or proxy problem, not a broken update cache.
4. **What does the error code say?** Note the exact code under *Settings → Windows Update → Update history*. Two different devices failing with the same code usually share a cause.

If none of these explain it, a corrupted update cache is the likely culprit. Common signs:

- The same update fails every time, often with `0x80070002` (files not found) or `0x80073712` (component files missing or damaged).
- Downloads restart from zero or never finish.
- Windows Update keeps showing an update you know is already installed.

## What "resetting the components" actually does

Windows keeps two working caches for updates:

| Folder | What it holds | Safe to rebuild? |
|---|---|---|
| `C:\Windows\SoftwareDistribution` | Downloaded update files and the update history database | Yes. Windows recreates it. The history list in Settings may look empty afterwards. |
| `C:\Windows\System32\catroot2` | Signature catalogs used to verify update packages | Yes. The Cryptographic service rebuilds it. |

Resetting means stopping the services that use these folders, renaming the folders so Windows builds fresh ones, and starting the services again.

**Rename the folders, don't delete them.** If something goes wrong, the old folders are still there to restore.

## Step by step: reset Windows Update components

Open Command Prompt as administrator and run these commands in order.

**1. Stop the services that hold the caches open:**

```
net stop wuauserv
net stop cryptSvc
net stop bits
net stop msiserver
```

`wuauserv` is Windows Update, `cryptSvc` owns catroot2, `bits` handles background downloads and `msiserver` is Windows Installer. If one says it was not running, that is fine. Carry on.

**2. Rename the two cache folders:**

```
ren C:\Windows\SoftwareDistribution SoftwareDistribution.old
ren C:\Windows\System32\catroot2 catroot2.old
```

If you get "Access is denied", a service is still running. Repeat step 1 and try again.

**3. Start the services again:**

```
net start wuauserv
net start cryptSvc
net start bits
net start msiserver
```

**4. Check for updates.** Go to *Settings → Windows Update → Check for updates*. The first check takes longer than usual because Windows is rebuilding its cache and re-downloading anything that was in progress.

Once updates install cleanly on that PC, you can delete the `.old` folders to recover the space.

## If it still fails: repair Windows itself

If the same update fails after a reset, the problem is usually in Windows' own component store, not the update cache. Run these two commands, in this order, from an elevated Command Prompt:

```
DISM /Online /Cleanup-Image /RestoreHealth
sfc /scannow
```

DISM repairs the component store (it may download clean files from Windows Update). System File Checker (`sfc`) then repairs protected system files using that store. Together they can take 15 to 30 minutes and use the disk heavily, so run them outside working hours where you can. Restart afterwards, then try the update again.

If a device still fails after all of this, consider an in-place repair upgrade or a rebuild. A PC that fails every month costs more in IT time than it is worth.

## Don't make the reset your first move

Resetting the components throws away every download in progress and makes the next update check slow. It is the right tool for a corrupted cache, and the wrong one for a full disk, a blocked proxy or a pending restart.

That is why the order matters:

1. Restart if a restart is pending.
2. Free disk space.
3. Fix connectivity.
4. Only then reset the components.
5. Then repair Windows with DISM and SFC.

On a fleet, write the order down and record which step fixed each device. A pattern usually shows up quickly, like a group of laptops that never restart or one site behind a proxy.

For the wider process of approvals, pilot rings and proving devices are current, see our [Windows patch management checklist](/blog/windows-patch-management-checklist/).

## Where SAVIO fits

[SAVIO](/savio/) is the AI System Administrator we build for Windows fleets. It follows the same order as this guide:

- **Evidence first.** The SAVIO agent reports each device's pending updates and the reason each one has not taken effect, such as a pending restart or the exact error code, before anyone tries a fix.
- **Cheap fixes are automatic.** Clearing temporary files and caches to free disk space is an automatic action.
- **Installs need approval.** Installing pending Windows updates needs IT approval, and SAVIO never restarts a device on its own.
- **The heavy fixes are gated.** Repairing system files (SFC) needs IT approval. Resetting the Windows Update components is admin-only, because it discards in-flight downloads.
- **Every attempt is audited**, with what was run, who approved it and the result.

If repeated update failures are eating your team's time, [book a 30-minute fleet assessment](/contact/). We will look at your Windows devices and your current patching routine, and tell you plainly whether SAVIO fits.
