"""What the BIOS reports, made trustworthy.

One place decides whether a serial number is real, used both at enrollment and on every hourly
hardware push. Locally assembled PCs (very common in India) and many motherboards ship the
firmware default — "To Be Filled By O.E.M.", "Default string", "System Serial Number" — and
storing that as a serial would make every such PC look like the same machine to an asset
register or a warranty lookup.
"""
from __future__ import annotations

import re

#: Firmware placeholders, compared case-insensitively after trimming.
_PLACEHOLDER_SERIALS = frozenset({
    "to be filled by o.e.m.",
    "to be filled by oem",
    "default string",
    "system serial number",
    "chassis serial number",
    "base board serial number",
    "serial number",
    "not specified",
    "not applicable",
    "none",
    "n/a",
    "na",
    "invalid",
    "oem",
    "o.e.m.",
    "123456789",
    "0123456789",
    "1234567890",
})

#: A serial made of one repeated character — "0000000000", "XXXXXXXX", "........".
_ONE_CHAR = re.compile(r"^(.)\1*$")


def clean_serial(value: str | None) -> str | None:
    """The serial if it is a real one, else None."""
    if value is None:
        return None
    v = value.strip()
    if len(v) < 3 or v.lower() in _PLACEHOLDER_SERIALS or _ONE_CHAR.match(v):
        return None
    return v[:100]


def clean_text(value: str | None) -> str | None:
    """Manufacturer / model as reported, unless it is a firmware placeholder. Assembled PCs
    report "To Be Filled By O.E.M." here too, and it must not reach an asset record."""
    if value is None:
        return None
    v = value.strip()
    return None if not v or v.lower() in _PLACEHOLDER_SERIALS else v


#: Manufacturer strings as BIOSes write them → the vendor name a warranty API is keyed on.
_VENDORS: tuple[tuple[str, str], ...] = (
    ("dell", "Dell"),
    ("hewlett-packard", "HP"),
    ("hewlett packard", "HP"),
    ("hp", "HP"),
    ("lenovo", "Lenovo"),
    ("microsoft", "Microsoft"),
    ("toshiba", "Toshiba"),
    ("dynabook", "Dynabook"),
    ("fujitsu", "Fujitsu"),
    ("acer", "Acer"),
    ("asustek", "ASUS"),
    ("asus", "ASUS"),
    ("micro-star", "MSI"),
    ("msi", "MSI"),
    ("apple", "Apple"),
    ("samsung", "Samsung"),
)


def normalize_vendor(manufacturer: str | None) -> str | None:
    """"Dell Inc." → "Dell", "HP"/"Hewlett-Packard" → "HP", "LENOVO" → "Lenovo".

    Matched on whole words at the start, so "HPE" and "Shopify" stay unknown. Unknown
    manufacturers (and placeholders) return None rather than a guess.
    """
    if not manufacturer:
        return None
    m = manufacturer.strip().lower()
    for prefix, vendor in _VENDORS:
        if m == prefix or m.startswith((prefix + " ", prefix + ",")):
            return vendor
    return None
