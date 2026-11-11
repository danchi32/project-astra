"""The software SAVIO may install (A2) — a server-side allowlist of winget package ids.

`install_package` accepts only an id from this map, the way `restart_service` accepts only a
name from SAFE_SERVICES: the portal never sends a free-form package id or installer URL, so
the push button can't become "run anything on every PC". The agent pins the same list
(`PackageInstaller.Catalog`), so a compromised or buggy backend can't widen it either; adding
a package needs an agent release, and `test_agent_catalog_matches` keeps the two equal.

No remote-access tools (AnyDesk, TeamViewer…): a technician could self-approve one onto a
thousand PCs, opening a remote channel outside SAVIO's own consented, audited remote support.

Machine-wide installs only: the agent runs as SYSTEM with `--scope machine`. That rules out
Microsoft Store-only apps (WhatsApp, for one), which install per user and can't be pushed
this way — they are left out rather than listed and failing.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogItem:
    winget_id: str
    name: str
    publisher: str
    category: str


CATALOG: dict[str, CatalogItem] = {i.winget_id: i for i in (
    CatalogItem("Google.Chrome", "Google Chrome", "Google", "Browser"),
    CatalogItem("Mozilla.Firefox", "Mozilla Firefox", "Mozilla", "Browser"),
    CatalogItem("Microsoft.Edge", "Microsoft Edge", "Microsoft", "Browser"),
    CatalogItem("Zoom.Zoom", "Zoom Workplace", "Zoom", "Meetings"),
    CatalogItem("Microsoft.Teams", "Microsoft Teams", "Microsoft", "Meetings"),
    CatalogItem("SlackTechnologies.Slack", "Slack", "Slack", "Meetings"),
    CatalogItem("Microsoft.Office", "Microsoft 365 Apps", "Microsoft", "Office"),
    CatalogItem("Adobe.Acrobat.Reader.64-bit", "Adobe Acrobat Reader", "Adobe", "Documents"),
    CatalogItem("Foxit.FoxitReader", "Foxit PDF Reader", "Foxit", "Documents"),
    CatalogItem("Notepad++.Notepad++", "Notepad++", "Notepad++", "Utilities"),
    CatalogItem("7zip.7zip", "7-Zip", "Igor Pavlov", "Utilities"),
    CatalogItem("VideoLAN.VLC", "VLC media player", "VideoLAN", "Utilities"),
    CatalogItem("Microsoft.PowerToys", "Microsoft PowerToys", "Microsoft", "Utilities"),
    CatalogItem("Google.GoogleDrive", "Google Drive", "Google", "Cloud storage"),
    CatalogItem("Dropbox.Dropbox", "Dropbox", "Dropbox", "Cloud storage"),
    CatalogItem("Microsoft.VisualStudioCode", "Visual Studio Code", "Microsoft", "Developer"),
    CatalogItem("Git.Git", "Git", "Git", "Developer"),
    CatalogItem("Python.Python.3.12", "Python 3.12", "Python Software Foundation", "Developer"),
)}
