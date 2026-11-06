---
title: "Internet Not Working on One Windows PC? Flush DNS, Renew IP, Reset Winsock"
description: "When one Windows PC can't load websites but others can: a step-by-step fix in the right order, from flushing DNS and renewing the IP address to a full Winsock and TCP/IP reset, with the commands for each."
date: "2026-10-31"
author: "Technomate IT-Solution"
keywords:
  - internet not working Windows
  - flush DNS
  - ipconfig release renew
  - netsh winsock reset
  - DNS_PROBE_FINISHED_NXDOMAIN
  - network reset Windows 11
faq:
  - q: "What does ipconfig /flushdns do?"
    a: "It clears the PC's cache of recent website name lookups. It is instant and safe, and fixes websites that fail because the PC remembers an old or wrong address."
  - q: "Is netsh winsock reset safe?"
    a: "It is safe but heavier than it looks. It needs a restart, can remove components installed by VPN or security software, and may clear a static IP address. Try flushing DNS, renewing the IP and restarting the adapter first."
  - q: "Why can I ping 8.8.8.8 but not open websites?"
    a: "The PC is online but can't turn website names into addresses, which is a DNS problem. Flush the DNS cache, then check which DNS servers the adapter is using."
  - q: "What does an IP address starting with 169.254 mean?"
    a: "The PC did not get an address from the network. Check the cable or Wi-Fi connection, then restart the network adapter."
---

Everyone else in the office is online. One PC can't load websites, or Teams connects but the browser says `DNS_PROBE_FINISHED_NXDOMAIN`, or the network icon shows "No internet" on a cable that clearly works.

When the problem is limited to one PC, the fix is almost always on that PC. This guide goes from the lightest fix to the heaviest. Stop as soon as the connection is back. Several of the commands need an **elevated** Command Prompt (run as administrator).

## Step 0: confirm it's only this PC

- If other devices on the same network are also offline, the problem is the router, the ISP or the firewall. Nothing on this PC will fix it.
- If only this PC is affected, note **what** fails. Can it reach an IP address but not a website name? Does nothing work at all?

A quick test from Command Prompt:

```
ping 8.8.8.8
ping google.com
```

If the first works and the second fails, it is a **DNS** problem: the PC is online but can't turn names into addresses. Start at Step 1. If both fail, start at Step 2.

## Step 1: flush the DNS cache

Windows keeps a cache of recent name lookups. If an entry is stale, for example after a website moved or a VPN changed DNS servers, the PC keeps going to the wrong address.

```
ipconfig /flushdns
```

It is instant and safe. Close and reopen the browser, then try again. Clearing the browser's own cache can also help if only certain websites fail.

## Step 2: renew the IP address

A PC can hold on to an address from a network it is no longer on, after a VPN, a docking station or a move between offices. Ask the network for a fresh one:

```
ipconfig /release
ipconfig /renew
```

`/release` drops the connection for a moment. Don't run it over a remote session to that same PC, because you will lose the session.

If `/renew` hangs or gives an address starting with `169.254`, the PC is not getting an address from the network at all. Check the cable or Wi-Fi, then go to Step 3.

## Step 3: restart the network adapter

Disabling and re-enabling the adapter clears many driver-level glitches:

1. Open *Settings → Network & internet → Advanced network settings*.
2. Choose **Disable** next to the adapter in use (Ethernet or Wi-Fi), wait a few seconds, then **Enable**.

This also drops every connection on that PC briefly, including remote support tools.

## Step 4: reset Winsock and the TCP/IP stack

If the steps above did not work, the network configuration itself may be corrupted, often by VPN clients, security software or proxy tools that hook into it. Reset it from an elevated Command Prompt, in this order:

```
netsh winsock reset
netsh int ip reset
```

Then **restart the PC**. Neither change takes effect until it does.

Be aware this is heavier than it looks:

- Some VPN and security products install components that a Winsock reset removes. They may need repairing or reinstalling afterwards.
- A static IP address on the adapter may need re-entering.

## Step 5: Windows' built-in Network reset

As a last resort before deeper diagnosis, Windows 10 and 11 can reinstall every network adapter and return network settings to defaults: *Settings → Network & internet → Advanced network settings → Network reset*.

It needs a restart, forgets saved Wi-Fi networks, and has the same VPN side effects as Step 4. Use it when nothing lighter worked.

## The order matters

Each step is more disruptive than the one before. Flushing DNS affects nothing. A Winsock reset needs a restart and can break a VPN client. Going straight to the heaviest fix turns a two-second problem into a half-day ticket.

On a fleet, write the order down and record which step fixed each device. If the same PCs keep needing Step 4, look at what's installed on them. A VPN or security agent is the usual suspect.

## Where SAVIO fits

[SAVIO](/savio/) is the AI System Administrator we build for Windows fleets. It follows the same order as this guide and applies a different level of trust to each step:

- **Light fixes are automatic.** Flushing DNS, renewing the IP address, restarting the network adapter and clearing the browser cache are all automatic actions, and each one reports its result.
- **The heavy fix needs approval.** Resetting Winsock and the TCP/IP stack requires IT approval, because it needs a restart and can affect VPN software.
- **Evidence first.** SAVIO looks at the device's network state before choosing a step, rather than running every fix in turn.
- **Everything is audited**, so repeat offenders show up.

If "internet not working" tickets keep pulling your team away from real work, [book a 30-minute fleet assessment](/contact/). We will show you what can safely be automated on your Windows devices.
