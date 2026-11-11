"""Is this machine's Windows activated, and was it activated by a crack?

Pure functions over what the agent reports (``DeviceLicensing`` rows) plus the app and
service inventory the backend already has. The signature lists live here, not in the agent,
so they can grow without an agent release.

Two separate questions, deliberately:

* **Activated?** — Windows only. Office is NOT judged here: on a machine where Microsoft 365
  is properly licensed through the subscription (a different licensing stack), SPP still lists
  placeholder ``Office16O365…R_Grace`` products in notification mode. Seen on a real,
  correctly licensed laptop while building this — calling that "not activated" would be a false
  alarm on every Microsoft 365 customer.
* **Activated by a crack?** — Windows and Office both. A KMS host on the loopback address or on
  the machine itself means a local KMS emulator (KMSpico, KMSAuto and friends); a known public
  piracy KMS server means the same thing done remotely; an activator in the app or service
  list is the tool itself. These say "Licensed" to Windows, which is exactly why the first
  question alone can't catch them.

A KMS host that is none of those is reported as-is and not flagged: it is most likely the
organisation's own KMS server.
"""
from __future__ import annotations

from collections.abc import Iterable

WINDOWS = "windows"
OFFICE = "office"

#: SPP LicenseStatus → what an IT person would call it.
_STATUS_TEXT = {
    0: "Not activated (unlicensed)",
    1: "Activated",
    2: "Not activated (initial grace period)",
    3: "Not activated (grace period after a hardware change)",
    4: "Non-genuine grace period",
    5: "Not activated (notification mode)",
    6: "Not activated (extended grace period)",
}

#: Public KMS servers that exist to activate pirated copies. Suffix-matched, so a sibling host
#: of the same service is caught too. Only hosts we are sure of — a corporate KMS wrongly on
#: this list would accuse a customer of piracy.
PIRACY_KMS_DOMAINS: frozenset[str] = frozenset({
    "msguides.com",
    "digiboy.ir",
    "03k.org",
})

#: Substrings of installed-app or service names that identify an activator. Lower-case.
ACTIVATOR_SIGNATURES: tuple[str, ...] = (
    "kmspico",
    "kmsauto",
    "kms_vl_all",
    "kmseldi",       # the KMSpico / KMSAuto background service
    "autokms",
    "microsoft toolkit",
    "hwidgen",
    "re-loader",
)

_LOOPBACK = {"localhost", "::1", "0.0.0.0"}


def windows_activation(rows: Iterable) -> tuple[str, str]:
    """(status, detail) for the ``genuine_windows`` check: pass / fail / unknown."""
    windows = [r for r in rows if r.kind == WINDOWS]
    if not windows:
        return "unknown", "Not reported yet (needs agent 0.14+)"
    licensed = [r for r in windows if r.license_status == 1]
    if licensed:
        channel = licensed[0].channel
        return "pass", f"Activated ({channel})" if channel else "Activated"
    readable = [r for r in windows if r.license_status in _STATUS_TEXT]
    if not readable:
        return "unknown", "Activation state unreadable"
    return "fail", _STATUS_TEXT[readable[0].license_status]


def _is_piracy_kms(host: str, hostname: str | None) -> bool:
    h = host.strip().lower().rstrip(".")
    if h in _LOOPBACK or h.startswith("127."):
        return True
    if hostname and h.split(".")[0] == hostname.strip().lower():
        return True       # a KMS emulator running on this very machine
    return any(h == d or h.endswith("." + d) for d in PIRACY_KMS_DOMAINS)


def activation_tool_findings(
    rows: Iterable,
    names: Iterable[str],
    hostname: str | None,
) -> list[str]:
    """Human-readable reasons this device looks crack-activated; empty when it doesn't.

    ``names`` is installed-app and service names together — an activator shows up as either.
    """
    findings: list[str] = []
    for r in rows:
        if r.kms_host and _is_piracy_kms(r.kms_host, hostname):
            what = "Windows" if r.kind == WINDOWS else "Office"
            findings.append(f"{what} activated against KMS host '{r.kms_host}'")
    seen: set[str] = set()
    for n in names:
        lowered = (n or "").lower()
        if any(sig in lowered for sig in ACTIVATOR_SIGNATURES) and lowered not in seen:
            seen.add(lowered)
            findings.append(f"Activator present: {n}")
    return findings
