---
title: "No Sound or Microphone Not Working on Windows? Fix It Before Your Next Meeting"
description: "Headset not detected, no sound in Teams or Zoom, or the mic silent on a Windows 10 or 11 PC? Quick checks, microphone privacy settings, restarting the Windows audio services, and fixing devices Windows stopped seeing."
date: "2026-11-05"
author: "Technomate IT-Solution"
keywords:
  - no sound Windows 11
  - microphone not working Windows
  - headset not detected
  - restart Windows Audio service
  - Teams microphone not working
  - Audio Endpoint Builder
---

"I can't hear anyone" and "they can't hear me" usually arrive two minutes before an important call. In most cases the fix takes less time than the ticket.

This guide covers the usual causes on business Windows 10 and Windows 11 PCs, from the quickest check to the deeper fixes. The service commands need an **elevated** Command Prompt (run as administrator).

## Step 1: the 30-second checks

- **Is the right device selected?** Click the speaker icon in the taskbar and check the output device. After plugging in a dock, monitor or headset, Windows often switches to a different one, such as the monitor's speakers.
- **Is it muted?** Check the Windows volume, the headset's own mute button, and the mute button inside the meeting app.
- **Does the meeting app agree?** Teams and Zoom have their own device settings. They can point at a different microphone and speaker than Windows does. Check the device settings in the app.
- **Unplug and replug.** For USB and Bluetooth headsets, reconnecting is often enough.

## Step 2: microphone works nowhere? Check privacy settings

If the microphone shows up in Windows but no app can hear it, Windows may be blocking access:

1. Open *Settings → Privacy & security → Microphone*.
2. Make sure **Microphone access** is on.
3. Make sure **Let apps access your microphone** is on, and that the meeting app is allowed.
4. Also allow **desktop apps** to access the microphone. Classic Teams, Zoom and most business apps count as desktop apps.

This setting can be changed by a policy, an update or the user. It is worth checking early because it looks exactly like a broken microphone.

## Step 3: restart the Windows audio services

If the right device is selected and nothing works, the audio services may be stuck. Two services matter:

- **Audio Endpoint Builder** (`AudioEndpointBuilder`) builds the list of speakers and microphones.
- **Windows Audio** (`Audiosrv`) plays and records sound, and depends on the Endpoint Builder.

Restart them from an elevated Command Prompt:

```
net stop audiosrv
net stop audioendpointbuilder
net start audioendpointbuilder
net start audiosrv
```

Stop Windows Audio first, because it depends on the Endpoint Builder. Then start them in the reverse order. Restarting only Windows Audio often fixes nothing, because the device list is held by the Endpoint Builder.

Sound goes silent for a few seconds while they restart. Rejoin the meeting afterwards.

## Step 4: the device isn't showing up at all

If a headset, dock or USB device is plugged in but Windows doesn't list it:

1. Open **Device Manager** (right-click Start → Device Manager).
2. Choose *Action → Scan for hardware changes*. This makes Windows look for new devices again without installing or changing anything.
3. Look under **Audio inputs and outputs** and **Sound, video and game controllers** for the device, or for a warning icon.

If the device appears with a warning icon, a driver update from the PC or headset manufacturer is usually the next step. Try a different USB port too, especially directly on the PC rather than through a hub or dock.

## Step 5: still nothing?

- Run the built-in troubleshooter: *Settings → System → Sound → Troubleshoot common sound problems*.
- Test the headset on another PC to rule out the hardware itself.
- Restart the PC. It is slower than the steps above but resets everything at once.

## Fewer audio tickets across the office

- **Standardise headsets** where possible. Fewer models means fewer driver surprises.
- **Keep dock and audio drivers current** across the fleet, especially on laptops that move between docks.
- **Check the microphone privacy setting** in your standard device setup, so it is not turned off by default.
- **Track the tickets.** If one dock or headset model causes most of them, replace it.

## Where SAVIO fits

[SAVIO](/savio/) is the AI System Administrator we build for Windows fleets. For audio problems:

- **Recovering the audio stack is automatic.** SAVIO restarts the Audio Endpoint Builder and Windows Audio together, in the right order, for "no sound" or "my mic isn't working". Nothing is reconfigured.
- **Scanning for hardware changes is automatic.** For a headset or dock Windows stopped seeing, SAVIO runs the same scan as Device Manager. It installs nothing and changes no driver.
- **Meeting apps restart automatically.** SAVIO can close and reopen Teams or Zoom when the app itself is stuck.
- **Every action is audited**, so a problem headset model shows up in the data.

If meeting-day tickets keep interrupting your team, [book a 30-minute fleet assessment](/contact/). We will show you what can safely be automated on your Windows devices.
