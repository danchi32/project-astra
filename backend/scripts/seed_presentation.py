"""Seed a presentation-grade demo tenant.

Builds one organization ("Technomate IT Solution", `is_demo`) with an invented 18-device
fleet, telemetry, remediation history across all three approval tiers, knowledge base,
asset register, notifications, audit trail and AI conversations — so every portal
module can be demoed without showing any customer's data. A real machine enrolled into
it afterwards (the org enrollment key) sits alongside the invented ones.

Idempotent: re-running wipes and rebuilds ONLY this org's rows — including any real
machine enrolled into it, which must then re-enroll. It refuses to touch an org of the
same name that is not flagged `is_demo`.

Local (no ASTRA_DATABASE_URL set): targets the same SQLite file as run_demo.py.

    backend/.venv/Scripts/python.exe backend/scripts/seed_presentation.py
    Sign in with:  demo@technomateai.com / AstraDemo2026!

Production: run as a Cloud Run Job, like print_public_stats.py, so the database
credential never leaves GCP. ASTRA_DEMO_PASSWORD is required there — the local password
is in this file and would be a public door into an org holding a real machine.

    gcloud run jobs deploy astra-seed-demo --image <image> --region asia-southeast1 \
      --set-secrets ASTRA_DATABASE_URL=ASTRA_DATABASE_URL:latest,\
ASTRA_JWT_SECRET_KEY=ASTRA_JWT_SECRET_KEY:latest,ASTRA_SECRETS_KEY=ASTRA_SECRETS_KEY:latest \
      --set-env-vars ASTRA_DEMO_PASSWORD=<chosen> \
      --command python --args scripts/seed_presentation.py
    gcloud run jobs execute astra-seed-demo --region asia-southeast1 --wait

In production the schema is Alembic's (0060 adds `is_demo`), the Freshservice
integration is seeded disabled (an enabled one would call a real third-party host with
an invented key), and the other staff accounts get unusable random passwords.
"""
import asyncio
import hashlib
import os
import random
import secrets
import sys
from datetime import datetime, timedelta, timezone

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

def _load_dotenv() -> None:
    """Load backend/.env the way run_demo.py does, so the credential this script encrypts
    is one the running backend can decrypt. Without it the two disagree about
    ASTRA_SECRETS_KEY and the portal reports the saved key as unreadable."""
    env_path = os.path.join(BACKEND_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# A database URL supplied from outside means a real deployment; none means the local demo.
LOCAL = "ASTRA_DATABASE_URL" not in os.environ

if LOCAL:
    DB_PATH = os.path.join(BACKEND_DIR, "astra-demo.db").replace("\\", "/")
    os.environ["ASTRA_DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_PATH}"
    os.environ.setdefault("ASTRA_JWT_SECRET_KEY", "demo-secret-key-local-only-not-for-prod")
    # ASTRA_SECRETS_KEY comes from backend/.env (loaded above), the same file run_demo.py
    # reads — so the seeded helpdesk credential is one the running backend can decrypt.
    # Not written here: a literal Fernet key is what the secret scan exists to stop.
elif not os.environ.get("ASTRA_DEMO_PASSWORD"):
    sys.exit("ASTRA_DEMO_PASSWORD is required outside the local demo database.")

from sqlalchemy import delete, select  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    AcknowledgementStatus,
    Asset,
    AssetCategory,
    AssetStatus,
    AuditLog,
    BannedSoftware,
    Base,
    Conversation,
    Device,
    DeviceEventLog,
    DeviceGroup,
    DeviceGroupMember,
    DeviceInstalledApp,
    DeviceService,
    DeviceSession,
    DeviceWindowsUpdate,
    EscalationState,
    HelpdeskSettings,
    KnowledgeArticle,
    KnowledgeSource,
    Location,
    Message,
    MessageRole,
    Notification,
    NotificationCategory,
    NotificationSeverity,
    Organization,
    OrganizationSettings,
    RemediationSource,
    RemediationStatus,
    RemediationTask,
    SubscriptionStatus,
    SupportEscalation,
    TelemetryDailyRollup,
    TelemetrySnapshot,
    User,
    UserRole,
    UserTeam,
    UserTeamMember,
)
from app.models.telemetry import (  # noqa: E402
    UPDATE_FAILED,
    UPDATE_INSTALLED,
    UPDATE_PENDING,
    UPDATE_PENDING_RESTART,
)
from app.core import crypto  # noqa: E402
from app.services.ai.aliases import embedding_text  # noqa: E402
from app.services.ai.embeddings import HashingEmbeddingProvider  # noqa: E402

ORG_NAME = "Technomate IT Solution"
ADMIN_EMAIL = "demo@technomateai.com"
ADMIN_PASSWORD = "AstraDemo2026!" if LOCAL else os.environ["ASTRA_DEMO_PASSWORD"]
# The technicians and directory users are scenery. Outside the local demo nobody signs in
# as them, so they get a password nobody knows.
STAFF_PASSWORD = ADMIN_PASSWORD if LOCAL else secrets.token_urlsafe(32)

# Fixed seed: the same fleet every run, so screenshots stay reproducible.
rng = random.Random(20260813)
NOW = datetime.now(timezone.utc)


def ago(**kw) -> datetime:
    return NOW - timedelta(**kw)


# ── Fleet definition ───────────────────────────────────────────────────────
# (hostname, user, os, model, cpu, ram_gb, disk_gb, minutes_since_seen, usb_blocked)
FLEET = [
    ("TM-FIN-0142", "priya.raman",   "Windows 11 Pro 24H2", "Latitude 7450",   "Intel Core Ultra 7 155U", 16,  512,    1, True),
    ("TM-FIN-0143", "james.okoro",   "Windows 11 Pro 24H2", "Latitude 7450",   "Intel Core Ultra 7 155U", 16,  512,    2, True),
    ("TM-FIN-0151", "hana.suzuki",   "Windows 11 Pro 23H2", "Latitude 5540",   "Intel Core i7-1355U",     16,  512,    1, True),
    ("TM-OPS-0208", "marcus.webb",   "Windows 11 Pro 24H2", "EliteBook 840 G11", "Intel Core Ultra 5 125U", 32, 1024,   3, True),
    ("TM-OPS-0209", "linda.perez",   "Windows 11 Pro 23H2", "EliteBook 840 G10", "Intel Core i5-1345U",   16,  512,    2, True),
    ("TM-OPS-0210", "tom.becker",    "Windows 10 Pro 22H2", "EliteBook 850 G8", "Intel Core i5-1135G7",   8,   256,    4, False),
    ("TM-ENG-0301", "sofia.marino",  "Windows 11 Pro 24H2", "ThinkPad P16s",   "AMD Ryzen 7 PRO 7840U",   32, 1024,    1, True),
    ("TM-ENG-0303", "chen.wei",      "Windows 11 Pro 23H2", "ThinkPad T14s",   "AMD Ryzen 5 PRO 7540U",   16,  512,    6, True),
    ("TM-ENG-0304", "olivia.hart",   "Windows 11 Pro 24H2", "ThinkPad T14s",   "AMD Ryzen 5 PRO 7540U",   16,  512,    2, True),
    ("TM-SAL-0407", "greg.donovan",  "Windows 10 Pro 22H2", "Surface Laptop 4", "Intel Core i5-1145G7",   8,  256, 2880, False),
    ("TM-HR-0502",  "peter.lindqvist", "Windows 11 Pro 23H2", "Latitude 5440", "Intel Core i5-1335U",     16,  512,    5, True),
    ("TM-PLT-0603", "qa.station",    "Windows 10 Pro 22H2", "OptiPlex 5090",   "Intel Core i5-10500T",     8,  256,    9, False),
    ("TM-WH-0701",  "warehouse.scan1", "Windows 11 Pro 23H2", "ThinkCentre M70q", "Intel Core i5-13400T", 16,  256,    3, True),
    ("TM-WH-0702",  "warehouse.scan2", "Windows 11 Pro 23H2", "ThinkCentre M70q", "Intel Core i5-13400T", 16,  256, 5760, True),
    ("TM-EXE-0801", "eleanor.voss",  "Windows 11 Pro 24H2", "XPS 14",          "Intel Core Ultra 7 155H", 32, 1024,    1, True),
    ("TM-EXE-0802", "robert.chase",  "Windows 11 Pro 24H2", "XPS 14",          "Intel Core Ultra 7 155H", 32, 1024,    4, True),
    ("TM-SRV-0901", "svc.fileshare", "Windows Server 2022", "PowerEdge R650",  "Intel Xeon Silver 4310",  64, 4096,    1, True),
    ("TM-SRV-0902", "svc.print",     "Windows Server 2022", "PowerEdge R650",  "Intel Xeon Silver 4310",  64, 2048,    1, True),
]

VENDOR_BY_MODEL = {
    "Latitude": "Dell Inc.", "OptiPlex": "Dell Inc.", "XPS": "Dell Inc.", "PowerEdge": "Dell Inc.",
    "EliteBook": "HP Inc.", "ThinkPad": "Lenovo", "ThinkCentre": "Lenovo", "Surface": "Microsoft",
}

# Devices carrying a deliberate problem, so the dashboard has something to show.
DISK_PRESSURE = {"TM-OPS-0210": 4.2, "TM-PLT-0603": 6.8, "TM-SAL-0407": 9.1}
RAM_PRESSURE = {"TM-FIN-0142": 0.93, "TM-ENG-0303": 0.88}
CPU_PRESSURE = {"TM-PLT-0603": 94.0, "TM-ENG-0303": 81.0}

BASE_APPS = [
    ("Microsoft 365 Apps for enterprise", "16.0.18324.20168", "Microsoft Corporation"),
    ("Microsoft Teams", "24193.1805.3040.8975", "Microsoft Corporation"),
    ("Google Chrome", "138.0.7204.97", "Google LLC"),
    ("Microsoft Edge", "138.0.3351.65", "Microsoft Corporation"),
    ("Adobe Acrobat Reader", "25.001.20521", "Adobe Inc."),
    ("Zoom Workplace", "6.5.1.4235", "Zoom Video Communications"),
    ("7-Zip 24.09", "24.09", "Igor Pavlov"),
    ("Notepad++", "8.7.9", "Notepad++ Team"),
    ("Microsoft Visual C++ 2015-2022 Redistributable", "14.42.34433", "Microsoft Corporation"),
    ("Windows Defender ATP Sensor", "10.8760.28000.1050", "Microsoft Corporation"),
    ("ASTRA Agent", "0.8.2", "Technomate IT-Solution"),
    ("Dell Command | Update", "5.4.0", "Dell Inc."),
    ("Cisco AnyConnect Secure Mobility Client", "4.10.08029", "Cisco Systems"),
    ("SAP GUI for Windows 8.00", "8.00.101", "SAP SE"),
    ("AutoCAD 2025", "25.0.128.0", "Autodesk"),
]

BASE_SERVICES = [
    ("Spooler", "Print Spooler", "Running", "Automatic"),
    ("WSearch", "Windows Search", "Running", "Automatic"),
    ("wuauserv", "Windows Update", "Running", "Manual"),
    ("BITS", "Background Intelligent Transfer Service", "Running", "Automatic"),
    ("Dnscache", "DNS Client", "Running", "Automatic"),
    ("WinDefend", "Microsoft Defender Antivirus Service", "Running", "Automatic"),
    ("MpsSvc", "Windows Defender Firewall", "Running", "Automatic"),
    ("Dhcp", "DHCP Client", "Running", "Automatic"),
    ("LanmanWorkstation", "Workstation", "Running", "Automatic"),
    ("EventLog", "Windows Event Log", "Running", "Automatic"),
    ("AstraAgentService", "ASTRA Agent Service", "Running", "Automatic"),
    ("SysMain", "SysMain", "Running", "Automatic"),
    ("RemoteRegistry", "Remote Registry", "Stopped", "Disabled"),
]

EVENT_TEMPLATES = [
    ("Application", "Outlook", 1000, "Error",
     "Faulting application name: OUTLOOK.EXE, version 16.0.18324.20168, faulting module: "
     "MAPI32.DLL. The application stopped responding while opening a large mailbox."),
    ("Application", "Application Hang", 1002, "Error",
     "The program OUTLOOK.EXE version 16.0.18324.20168 stopped interacting with Windows and was closed."),
    ("System", "disk", 51, "Warning",
     "An error was detected on device \\Device\\Harddisk0\\DR0 during a paging operation."),
    ("System", "Service Control Manager", 7031, "Error",
     "The Print Spooler service terminated unexpectedly. It has done this 3 time(s)."),
    ("System", "Microsoft-Windows-WindowsUpdateClient", 20, "Error",
     "Installation Failure: Windows failed to install the following update with error 0x80070643."),
    ("Application", "ESENT", 455, "Warning",
     "svchost (1284) failed to open the log file. The database engine will retry."),
    ("System", "Microsoft-Windows-Kernel-Power", 41, "Error",
     "The system has rebooted without cleanly shutting down first."),
    ("Application", "MsiInstaller", 11708, "Warning",
     "Product: Microsoft 365 Apps for enterprise -- Repair completed successfully."),
    ("System", "Microsoft-Windows-Time-Service", 134, "Warning",
     "NtpClient was unable to set a domain peer to use as a time source. Will retry in 15 minutes."),
    ("System", "Microsoft-Windows-DNS-Client", 1014, "Warning",
     "Name resolution for intranet.technomateai.com timed out after none of the configured "
     "DNS servers responded."),
    ("Application", "Microsoft-Windows-Winlogon", 6000, "Information",
     "The winlogon notification subscriber <GPClient> took 62 second(s) to handle the "
     "notification event (Logon)."),
    ("System", "Microsoft-Windows-Kernel-PnP", 219, "Warning",
     "The driver \\Driver\\WudfRd failed to load for the device USB\\VID_046D."),
]

UPDATES = [
    ("KB5062553", "2026-07 Cumulative Update for Windows 11 Version 24H2 (x64)"),
    ("KB5062045", "2026-07 Cumulative Update for .NET Framework 3.5 and 4.8.1"),
    ("KB5061768", "2026-06 Servicing Stack Update for Windows 11"),
    ("KB5060842", "Security Intelligence Update for Microsoft Defender Antivirus"),
    ("KB5059502", "2026-05 Cumulative Update for Windows 11 Version 23H2 (x64)"),
]


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def vendor_for(model: str) -> str:
    for key, vendor in VENDOR_BY_MODEL.items():
        if key in model:
            return vendor
    return "Unknown"


async def wipe(session, org_id) -> None:
    """Drop only this demo org's rows so the script is safely re-runnable."""
    device_ids = (await session.execute(select(Device.id).where(Device.org_id == org_id))).scalars().all()
    if device_ids:
        for model in (TelemetrySnapshot, TelemetryDailyRollup, DeviceEventLog,
                      DeviceInstalledApp, DeviceService, DeviceWindowsUpdate,
                      DeviceSession, DeviceGroupMember):
            await session.execute(delete(model).where(model.device_id.in_(device_ids)))
    conv_ids = (await session.execute(
        select(Conversation.id).where(Conversation.org_id == org_id)
    )).scalars().all()
    if conv_ids:
        await session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
    # Team members go before users, and group members before devices: both hang off rows
    # the loop below is about to delete.
    team_ids = (await session.execute(
        select(UserTeam.id).where(UserTeam.org_id == org_id)
    )).scalars().all()
    if team_ids:
        await session.execute(delete(UserTeamMember).where(UserTeamMember.team_id.in_(team_ids)))
    for model in (DeviceGroup, UserTeam,
                  Conversation, RemediationTask, Asset, Notification, AuditLog,
                  KnowledgeArticle, BannedSoftware, Location, Device, User,
                  SupportEscalation, HelpdeskSettings, OrganizationSettings):
        await session.execute(delete(model).where(model.org_id == org_id))
    await session.flush()


async def main() -> None:
    if LOCAL:
        # Production's schema belongs to Alembic; only the throwaway SQLite file is built here.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    embedder = HashingEmbeddingProvider()

    async with SessionLocal() as s:
        org = (await s.execute(select(Organization).where(Organization.name == ORG_NAME))).scalar_one_or_none()
        if org is None:
            # No email_domain: the demo must not claim a real domain for signup matching.
            org = Organization(name=ORG_NAME, is_demo=True)
            s.add(org)
            await s.flush()
        elif not org.is_demo:
            # The wipe below deletes every row the org owns. A real organisation that
            # happens to have this name must never reach it.
            sys.exit(f"'{ORG_NAME}' exists and is not a demo org — refusing to touch it.")
        else:
            await wipe(s, org.id)

        org.plan = "expert"  # every feature a prospect might ask to see
        org.subscription_status = SubscriptionStatus.ACTIVE
        org.license_count = 250
        org.ai_pro = True
        org.current_period_end = NOW + timedelta(days=22)
        # A key printed in this file would let anyone enroll into an org holding a real
        # machine, so outside the local demo it is random (and rotates on every re-seed).
        org.agent_enrollment_key = "TM-ENROLL-7F3A-91C2-DEMO" if LOCAL else secrets.token_urlsafe(24)

        s.add(OrganizationSettings(
            org_id=org.id,
            auto_approve_automatic=True,
            require_admin_for_approval_tier=False,
            min_password_length=12,
            enrollment_token_default_days=14,
        ))

        # ── The helpdesk this org already runs ──────────────────────────────
        # Invented credential, encrypted with the demo key, so the portal shows a
        # connected integration instead of an empty setup form. Disabled outside the local
        # demo: enabled, an escalation would send the invented key to a real Freshservice host.
        s.add(HelpdeskSettings(
            org_id=org.id, provider="freshservice", enabled=LOCAL, domain="technomate",
            api_key_encrypted=crypto.encrypt("fsk_live_9K4mQ2xR7vTbZ81c"),
            default_priority=2, workspace_id=2, group_id=None,
            category_map={
                "restart_outlook": {"category": "Software", "sub_category": "Microsoft 365"},
                "office_repair": {"category": "Software", "sub_category": "Microsoft 365"},
                "restart_service": {"category": "Hardware", "sub_category": "Printing"},
                "clear_temp": {"category": "Hardware", "sub_category": "Storage"},
                "windows_update_install": {"category": "Software", "sub_category": "Patching"},
            },
            last_verified_at=ago(hours=6),
        ))

        # ── People ──────────────────────────────────────────────────────────
        admin = User(org_id=org.id, email=ADMIN_EMAIL, full_name="Priya Raman",
                     hashed_password=hash_password(ADMIN_PASSWORD), role=UserRole.ADMIN,
                     created_at=ago(days=210))
        tech = User(org_id=org.id, email="marcus.webb@technomateai.com", full_name="Marcus Webb",
                    hashed_password=hash_password(STAFF_PASSWORD), role=UserRole.TECHNICIAN,
                    created_at=ago(days=180))
        tech2 = User(org_id=org.id, email="hana.suzuki@technomateai.com", full_name="Hana Suzuki",
                     hashed_password=hash_password(STAFF_PASSWORD), role=UserRole.TECHNICIAN,
                     created_at=ago(days=96))
        # One shared hash for the directory users — bcrypt is deliberately slow and these
        # accounts exist for asset assignment, not for signing in during the demo.
        staff_hash = hash_password(STAFF_PASSWORD)
        staff = [
            User(org_id=org.id, email=f"{u}@technomateai.com",
                 full_name=" ".join(p.capitalize() for p in u.split(".")),
                 hashed_password=staff_hash,
                 role=UserRole.USER, created_at=ago(days=rng.randint(30, 200)))
            for u in ("james.okoro", "sofia.marino", "aisha.khan", "eleanor.voss",
                      "daniel.reyes", "nadia.farouk", "tom.becker", "olivia.hart")
        ]
        s.add_all([admin, tech, tech2, *staff])

        for name in ("HQ — Detroit", "Plant 2 — Toledo", "Warehouse — Columbus", "Remote / Field"):
            s.add(Location(org_id=org.id, name=name))
        for name, pattern in (("uTorrent", "utorrent"), ("BitTorrent", "bittorrent"),
                              ("TeamViewer (personal)", "teamviewer"), ("Hola VPN", "hola")):
            s.add(BannedSoftware(org_id=org.id, name=name, pattern=pattern))
        await s.flush()

        # ── Devices + telemetry ─────────────────────────────────────────────
        devices: dict[str, Device] = {}
        for host, user, osv, model, cpu, ram_gb, disk_gb, mins, usb in FLEET:
            # A device counts as online for 3 minutes after its last heartbeat, so anything
            # meant to look live is pinned inside that window — the two deliberately silent
            # machines keep their real age.
            mins = mins if mins > 60 else min(mins, 2)
            dev = Device(
                org_id=org.id, hostname=host, machine_id=sha(host)[:32], os_version=osv,
                serial_number=f"NW{sha(host)[:8].upper()}", agent_version="0.8.2",
                logged_in_user=f"TECHNOMATE\\{user}", token_hash=sha("enroll-" + host),
                last_seen_at=ago(minutes=mins), usb_storage_blocked=usb, is_active=True,
                manufacturer=vendor_for(model), model=model, cpu_name=cpu,
                total_ram_mb=ram_gb * 1024, total_storage_gb=float(disk_gb),
                created_at=ago(days=rng.randint(40, 200)),
            )
            if host in ("TM-SAL-0407", "TM-PLT-0603"):
                dev.agent_version = "0.8.0"
            s.add(dev)
            devices[host] = dev
        await s.flush()

        for host, user, osv, model, cpu, ram_gb, disk_gb, mins, usb in FLEET:
            dev = devices[host]
            ram_total = ram_gb * 1024
            ram_ratio = RAM_PRESSURE.get(host, rng.uniform(0.38, 0.68))
            cpu_now = CPU_PRESSURE.get(host, rng.uniform(6.0, 34.0))
            free_gb = DISK_PRESSURE.get(host, disk_gb * rng.uniform(0.35, 0.62))
            disks = [{"drive": "C:", "total_gb": float(disk_gb),
                      "used_gb": round(disk_gb - free_gb, 1), "free_gb": round(free_gb, 1)}]

            # ~2 hours of 60-second snapshots — enough for the detail-page chart.
            for i in range(120):
                jitter = rng.uniform(-0.06, 0.06)
                s.add(TelemetrySnapshot(
                    device_id=dev.id, org_id=org.id,
                    cpu_percent=round(max(1.0, min(99.0, cpu_now * (1 + jitter * 3))), 1),
                    ram_total_mb=ram_total,
                    ram_used_mb=int(ram_total * max(0.15, min(0.97, ram_ratio + jitter))),
                    disks=disks, collected_at=ago(minutes=mins + i),
                ))
            # 45 days of history for trend reporting.
            for d in range(45):
                jitter = rng.uniform(-0.08, 0.08)
                s.add(TelemetryDailyRollup(
                    device_id=dev.id, org_id=org.id, day=(NOW - timedelta(days=d)).date(),
                    samples=1380,
                    cpu_avg=round(max(2.0, cpu_now * (1 + jitter)), 1),
                    cpu_max=round(min(100.0, cpu_now * 1.9 + 8), 1),
                    ram_used_avg_mb=int(ram_total * max(0.15, ram_ratio + jitter)),
                    ram_used_max_mb=int(ram_total * min(0.98, ram_ratio + 0.14)),
                    disk_free_min_pct=round(free_gb / disk_gb * 100, 1),
                ))

            apps = list(BASE_APPS)
            if host == "TM-SAL-0407":
                apps.append(("uTorrent", "3.6.0", "BitTorrent Inc."))
            if host == "TM-PLT-0603":
                apps.append(("TeamViewer", "15.58.4", "TeamViewer Germany GmbH"))
            for name, ver, pub in apps:
                s.add(DeviceInstalledApp(
                    device_id=dev.id, org_id=org.id, name=name, version=ver, publisher=pub,
                    install_date=(NOW - timedelta(days=rng.randint(20, 400))).strftime("%Y%m%d"),
                    collected_at=ago(minutes=mins),
                ))

            for name, display, status, start in BASE_SERVICES:
                if host == "TM-PLT-0603" and name == "Spooler":
                    status = "Stopped"
                s.add(DeviceService(device_id=dev.id, org_id=org.id, name=name,
                                    display_name=display, status=status, start_type=start,
                                    collected_at=ago(minutes=mins)))

            # A healthy estate logs warnings, not errors. Only the known-problem devices
            # carry Error-level entries, so the fleet reports don't open on a wall of red
            # that the rest of the demo then has to explain away.
            noisy = host in ("TM-OPS-0210", "TM-PLT-0603", "TM-SAL-0407", "TM-WH-0702")
            pool = [e for e in EVENT_TEMPLATES if noisy or e[3] != "Error"]
            for _ in range(rng.randint(2, 4) if noisy else rng.randint(1, 2)):
                log, source, eid, level, msg = rng.choice(pool)
                s.add(DeviceEventLog(device_id=dev.id, org_id=org.id, log_name=log, source=source,
                                     event_id=eid, level=level, message=msg,
                                     occurred_at=ago(hours=rng.randint(1, 72))))

            # A well-run estate: most devices are fully patched. The three known-problem
            # devices carry the pending/failed updates, plus two waiting on a restart —
            # enough for the dashboard to have something real to act on.
            for i, (kb, title) in enumerate(UPDATES):
                if host in ("TM-SAL-0407", "TM-PLT-0603", "TM-OPS-0210"):
                    state = UPDATE_FAILED if i == 0 else (UPDATE_PENDING if i < 3 else UPDATE_INSTALLED)
                elif host in ("TM-HR-0502", "TM-WH-0702") and i == 0:
                    state = UPDATE_PENDING_RESTART
                else:
                    state = UPDATE_INSTALLED
                s.add(DeviceWindowsUpdate(
                    device_id=dev.id, org_id=org.id, kb_article_id=kb, title=title, state=state,
                    error_code="0x80070643" if state == UPDATE_FAILED else None,
                    installed_on=(NOW - timedelta(days=rng.randint(1, 40))).strftime("%Y-%m-%d")
                    if state == UPDATE_INSTALLED else None,
                    collected_at=ago(minutes=mins),
                ))

        # ── Device groups, user teams and logon sessions ────────────────────
        # Groups overlap on purpose: "Windows 10 — end of support" cuts across three
        # departments, which is the whole reason a group is not a location. The demo needs
        # that visible, because the fleet-wide push is aimed at exactly that kind of set.
        GROUPS = [
            ("Finance laptops", "Finance and payroll endpoints — SAP GUI, restricted USB.",
             "#2563eb", ("TM-FIN-0142", "TM-FIN-0143", "TM-FIN-0151")),
            ("Engineering workstations", "CAD and build machines. High spec, heavy disk churn.",
             "#059669", ("TM-ENG-0301", "TM-ENG-0303", "TM-ENG-0304")),
            ("Shop floor & warehouse", "Kiosks and scanning stations. Shared logins, no personal data.",
             "#ea580c", ("TM-PLT-0603", "TM-WH-0701", "TM-WH-0702")),
            ("Executive", "Board and leadership laptops. Every action on these is admin-only.",
             "#9a2fbb", ("TM-EXE-0801", "TM-EXE-0802")),
            ("Servers", "File and print. Never targeted by a bulk restart.",
             "#64748b", ("TM-SRV-0901", "TM-SRV-0902")),
            ("Windows 10 — end of support", "Cuts across departments. The migration worklist.",
             "#dc2626", ("TM-OPS-0210", "TM-SAL-0407", "TM-PLT-0603")),
        ]
        for name, desc, colour, members in GROUPS:
            g = DeviceGroup(org_id=org.id, name=name, description=desc, colour=colour,
                            created_at=ago(days=rng.randint(20, 120)))
            s.add(g)
            await s.flush()
            for host in members:
                s.add(DeviceGroupMember(group_id=g.id, device_id=devices[host].id))

        # Teams are the people, and they overlap too — the same engineer is on the service
        # desk rota and in endpoint engineering. Membership is NOT permission: RBAC still
        # decides what each of them may do.
        TEAMS = [
            ("Service desk", "First line. Rota covers 07:00–19:00 across both plants.",
             "#0891b2", (tech, tech2)),
            ("Endpoint engineering", "Owns the action allowlist, the agent build and rollout.",
             "#6d28d9", (admin, tech)),
            ("Security & compliance", "Reviews the audit trail and signs off admin-tier actions.",
             "#ca8a04", (admin, tech2)),
        ]
        for name, desc, colour, users in TEAMS:
            t = UserTeam(org_id=org.id, name=name, description=desc, colour=colour,
                         created_at=ago(days=rng.randint(20, 120)))
            s.add(t)
            await s.flush()
            for u in users:
                s.add(UserTeamMember(team_id=t.id, user_id=u.id))

        # Logon sessions. Every laptop reports its console session; the file server carries
        # the case the Devices page cannot express at all — several people signed in at once,
        # over RDP, from named client machines.
        # (hostname, session_id, username, state, connection, station, client, logon_h, idle_s)
        SESSIONS = [
            ("TM-SRV-0901", 0, None, "disconnected", "console", "Console", None, 720, None),
            ("TM-SRV-0901", 3, "TECHNOMATE\marcus.webb", "active", "rdp", "RDP-Tcp#3", "TM-OPS-0208", 4, 90),
            ("TM-SRV-0901", 5, "TECHNOMATE\hana.suzuki", "active", "rdp", "RDP-Tcp#5", "TM-FIN-0151", 2, 1500),
            ("TM-SRV-0901", 7, "TECHNOMATE\svc.backup", "disconnected", "rdp", "RDP-Tcp#7", "TM-SRV-0902", 26, 84000),
            ("TM-SRV-0902", 0, None, "disconnected", "console", "Console", None, 720, None),
            ("TM-SRV-0902", 2, "TECHNOMATE\marcus.webb", "disconnected", "rdp", "RDP-Tcp#2", "TM-OPS-0208", 19, 61000),
            # A kiosk sitting at the logon screen. "(no user)" is a real answer to
            # "who is on that machine", and the page says so rather than hiding the row.
            ("TM-PLT-0603", 1, None, "disconnected", "console", "Console", None, 9, None),
        ]
        # Idle time is the column that tells "working" from "left the desk", so the demo
        # needs both. Everything not named here reads as active.
        IDLE = {"TM-HR-0502": 4380, "TM-OPS-0209": 1020, "TM-ENG-0304": 2760,
                "TM-SAL-0407": 172800, "TM-WH-0702": 396000}
        overridden = {h for h, *_ in SESSIONS}
        for host, user, *_rest in FLEET:
            if host in overridden:
                continue
            SESSIONS.append((host, 1, f"TECHNOMATE\{user}", "active", "console", "Console",
                             None, rng.randint(1, 9), IDLE.get(host, rng.choice([30, 60, 120, 240]))))
        for host, sid, user, state, conn, station, client, logon_h, idle in SESSIONS:
            s.add(DeviceSession(
                device_id=devices[host].id, org_id=org.id, session_id=sid, username=user,
                state=state, connection=conn, station=station, client_name=client,
                logon_at=ago(hours=logon_h), idle_seconds=idle,
            ))
        for host in {h for h, *_ in SESSIONS}:
            devices[host].sessions_hash = sha(f"sessions-{host}")[:64]

        # Event evidence the hero conversation refers to.
        s.add(DeviceEventLog(
            device_id=devices["TM-FIN-0142"].id, org_id=org.id, log_name="Application",
            source="Application Hang", event_id=1002, level="Error",
            message="The program OUTLOOK.EXE version 16.0.18324.20168 stopped interacting with "
                    "Windows and was closed. Hang type: Top level window is idle.",
            occurred_at=ago(minutes=14),
        ))

        # ── Remediation history ─────────────────────────────────────────────
        auto_history = [
            ("restart_outlook", "TM-FIN-0142", "Outlook hang recorded (Event 1002) with RAM at 93%.",
             "Outlook restarted; the mailbox opened normally and RAM dropped to 61%.", 0.6),
            ("clear_temp", "TM-OPS-0210", "C: had 4.2 GB free (1.6% of 256 GB).",
             "Cleared 11.8 GB of user temp files; free space now 16.0 GB.", 3),
            ("clear_system_temp", "TM-OPS-0210", "Free space still below the 10% policy floor after the user clean.",
             "Cleared 6.4 GB from Windows Temp, Prefetch and the Update cache.", 2.8),
            ("flush_dns", "TM-ENG-0303", "Intranet name resolution failing; stale DNS entries suspected.",
             "Resolver cache flushed; internal hostnames resolve again.", 8),
            ("restart_service", "TM-PLT-0603", "Print Spooler terminated unexpectedly 3 times (Event 7031).",
             "Print Spooler restarted and has stayed running for 46 minutes.", 1.5),
            ("restart_teams", "TM-HR-0502", "Teams stuck on a cached session; user reported no message delivery.",
             "Teams restarted; session re-authenticated and messages delivered.", 5),
            ("restart_explorer", "TM-OPS-0208", "Taskbar unresponsive after a display driver event.",
             "Explorer shell restarted; desktop and taskbar responsive.", 11),
            ("clear_browser_cache", "TM-ENG-0304", "Intranet portal returning stale assets after a release.",
             "Chrome and Edge HTTP caches cleared; the portal loads the new build.", 20),
            ("restart_network_adapter", "TM-WH-0701", "Wi-Fi adapter dropped and did not re-associate.",
             "Adapter cycled; the device reconnected to TM-CORP at 866 Mbps.", 26),
            ("restart_chrome", "TM-EXE-0801", "Chrome holding 6.1 GB across 40 tabs; device paging heavily.",
             "Chrome restarted with tabs restored; 4.4 GB returned to the OS.", 30),
            ("restart_zoom", "TM-EXE-0802", "Zoom failed to open the meeting window before a client call.",
             "Zoom restarted; the meeting joined successfully.", 34),
            ("clear_temp", "TM-PLT-0603", "QA station below the free-space floor for a second day.",
             "Cleared 5.2 GB of temp files.", 40),
            ("restart_outlook", "TM-FIN-0143", "Outlook stopped syncing the shared finance mailbox.",
             "Outlook restarted; the shared mailbox resynchronised.", 46),
            ("flush_dns", "TM-OPS-0209", "VPN split-tunnel change left stale records cached.",
             "Resolver cache flushed after the VPN policy change.", 52),
            ("restart_service", "TM-SRV-0902", "Print queue stalled on the print server.",
             "Print Spooler restarted; 14 queued jobs released.", 58),
        ]
        for action, host, reason, outcome, hrs in auto_history:
            s.add(RemediationTask(
                org_id=org.id, device_id=devices[host].id, action_id=action,
                params={"service_name": "Spooler"} if action == "restart_service" else None,
                tier="automatic", status=RemediationStatus.SUCCEEDED, reason=reason,
                source=RemediationSource.ASSISTANT, from_llm=action in ("clear_system_temp", "restart_chrome"),
                result={"success": True, "output": outcome},
                completed_at=ago(hours=hrs), created_at=ago(hours=hrs + 0.05),
            ))

        pending = [
            ("office_repair", "TM-FIN-0151", "approval_required",
             "Word and Excel have crashed 6 times in 24 hours on this device (Event 1000, "
             "faulting module VBE7.DLL). An Office quick repair is the documented fix.", 0.3),
            ("windows_update_install", "TM-OPS-0210", "approval_required",
             "KB5062553 has failed to install 3 times (0x80070643). The device is 41 days "
             "behind the patch baseline.", 1.1),
            ("network_reset", "TM-WH-0702", "approval_required",
             "The scanner station has had no network for 4 days. Adapter restart did not "
             "recover it; a Winsock/TCP-IP reset is the next documented step.", 2.4),
            ("uninstall_application", "TM-SAL-0407", "admin_only",
             "uTorrent is installed and appears on the organisation's restricted-software "
             "list. Removal requires admin approval.", 3.6),
            ("registry_fix", "TM-PLT-0603", "admin_only",
             "Windows Search index is corrupt; the approved registry fix rebuilds the "
             "index catalogue. Admin approval required.", 5.2),
        ]
        for action, host, tier, reason, hrs in pending:
            s.add(RemediationTask(
                org_id=org.id, device_id=devices[host].id, action_id=action,
                params={"app_name": "uTorrent"} if action == "uninstall_application"
                else ({"fix_id": "rebuild_search_index"} if action == "registry_fix" else None),
                tier=tier, status=RemediationStatus.PENDING_APPROVAL, reason=reason,
                source=RemediationSource.ASSISTANT, from_llm=True,
                created_at=ago(hours=hrs),
            ))

        approved_done = [
            ("office_repair", "TM-ENG-0303", "approval_required",
             "Excel crashed repeatedly opening the production planning workbook.",
             "Office quick repair completed. Excel opened the workbook without incident.", 26),
            ("driver_update", "TM-EXE-0802", "approval_required",
             "Display driver reset loop after docking (Event 4101).",
             "Intel graphics driver updated to 32.0.101.6314; no resets in 18 hours.", 50),
            ("windows_update_install", "TM-HR-0502", "approval_required",
             "Device 28 days behind the patch baseline.",
             "3 updates installed. A restart is required to complete KB5062553.", 74),
        ]
        for action, host, tier, reason, outcome, hrs in approved_done:
            s.add(RemediationTask(
                org_id=org.id, device_id=devices[host].id, action_id=action, tier=tier,
                status=RemediationStatus.SUCCEEDED, reason=reason,
                source=RemediationSource.ASSISTANT, from_llm=True,
                approved_by_user_id=admin.id, result={"success": True, "output": outcome},
                completed_at=ago(hours=hrs), created_at=ago(hours=hrs + 1.5),
            ))

        s.add(RemediationTask(
            org_id=org.id, device_id=devices["TM-WH-0702"].id, action_id="restart_network_adapter",
            tier="automatic", status=RemediationStatus.FAILED,
            reason="Scanner station unreachable; adapter restart attempted.",
            source=RemediationSource.ASSISTANT,
            result={"success": False, "output": "Device did not check in within the 10-minute "
                                                "dispatch window. Escalated to IT."},
            completed_at=ago(hours=71), created_at=ago(hours=72),
        ))
        s.add(RemediationTask(
            org_id=org.id, device_id=devices["TM-PLT-0603"].id, action_id="reset_windows_update_components",
            tier="admin_only", status=RemediationStatus.REJECTED,
            reason="Windows Update component store suspected corrupt.",
            source=RemediationSource.ASSISTANT, approved_by_user_id=admin.id,
            created_at=ago(hours=96),
        ))
        s.add(RemediationTask(
            org_id=org.id, device_id=devices["TM-ENG-0301"].id, action_id="clear_temp",
            tier="automatic", status=RemediationStatus.DISPATCHED,
            reason="Build cache growth pushed C: below the 15% free-space warning line.",
            source=RemediationSource.USER, requested_by_user_id=tech.id,
            created_at=ago(minutes=3),
        ))

        # ── Knowledge base ──────────────────────────────────────────────────
        articles = [
            ("Outlook freezes when opening a large mailbox",
             "Symptom: Outlook stops responding when a shared or archive mailbox over ~15 GB is "
             "opened, usually with Event 1002 (Application Hang) in the Application log.\n\n"
             "Diagnosis: check RAM headroom first — the hang is almost always memory pressure, "
             "not mailbox corruption. Confirm the OST size under %LOCALAPPDATA%\\Microsoft\\Outlook.\n\n"
             "Fix: restart Outlook (automatic tier). If it recurs within the same day, reduce the "
             "cached-mail slider to 3 months, then rebuild the OST if it still recurs.",
             KnowledgeSource.MANUAL, None, None, 1, 0, True),
            ("Device runs out of disk space on C:",
             "Symptom: user reports the device is slow, Windows warns about low disk space, or "
             "updates fail to download.\n\nDiagnosis: check free space against the 10% policy floor. "
             "Temp files, the Windows Update download cache and Prefetch account for most of it.\n\n"
             "Fix: clear_temp first (user session), then clear_system_temp (elevated) if still below "
             "the floor. Both are automatic tier and self-rebuilding.",
             KnowledgeSource.MANUAL, None, None, 1, 0, True),
            ("Print Spooler stops repeatedly (Event 7031)",
             "Symptom: printing stops working; Service Control Manager logs Event 7031 for the "
             "Print Spooler.\n\nDiagnosis: usually a corrupt job in the spool folder or a bad "
             "third-party print driver.\n\nFix: restart_service on Spooler. If it recurs more than "
             "twice a week, clear %SystemRoot%\\System32\\spool\\PRINTERS and review drivers.",
             KnowledgeSource.MANUAL, None, None, 1, 0, True),
            ("VPN connects but internal sites do not resolve",
             "Symptom: the VPN tunnel is up but intranet hostnames fail while public sites work.\n\n"
             "Diagnosis: stale resolver cache after a split-tunnel or DNS suffix change.\n\n"
             "Fix: flush_dns (automatic tier). If it persists, confirm the DNS suffix search list "
             "pushed by the VPN profile.",
             KnowledgeSource.MANUAL, None, None, 1, 0, True),
            ("Windows Update fails with 0x80070643",
             "Symptom: a cumulative update repeatedly fails to install; WindowsUpdateClient logs "
             "Event 20 with 0x80070643.\n\nDiagnosis: usually a damaged .NET servicing payload or a "
             "partially applied servicing stack update.\n\nFix: install the latest SSU first, then "
             "retry the cumulative update (approval required). Reset Windows Update components "
             "(admin only) if two retries fail.",
             KnowledgeSource.MANUAL, None, None, 1, 0, True),
            ("Teams stuck on a cached session",
             "Captured from a confirmed fix. Users report Teams showing as connected while messages "
             "are neither sent nor received, typically after a password change.\n\nRestarting the "
             "Teams process clears the cached session state and forces re-authentication.",
             KnowledgeSource.RESOLVED_ISSUE, "restart_teams",
             ["teams not sending messages", "teams stuck", "teams says connected but nothing works"],
             14, 1, True),
            ("Chrome using excessive memory on 32 GB laptops",
             "Captured from a confirmed fix. Engineering laptops with 40+ tabs page heavily and the "
             "whole device becomes slow.\n\nRestarting Chrome returns the memory and restores the "
             "previous tabs, so the user loses nothing.",
             KnowledgeSource.RESOLVED_ISSUE, "restart_chrome",
             ["laptop very slow chrome", "chrome eating ram", "everything is laggy with chrome open"],
             9, 0, True),
            ("Explorer shell freezes after undocking",
             "Captured from a confirmed fix, still in learning: the taskbar and desktop stop "
             "responding after a monitor change. Restarting explorer.exe recovers the shell.",
             KnowledgeSource.RESOLVED_ISSUE, "restart_explorer",
             ["taskbar frozen", "desktop not responding after docking"],
             2, 0, False),
            ("Zoom will not open the meeting window",
             "Captured from a confirmed fix that has recently started failing. Restarting Zoom "
             "recovered the meeting window in most cases, but four recent attempts did not — "
             "review before recommending.",
             KnowledgeSource.RESOLVED_ISSUE, "restart_zoom",
             ["zoom won't open", "zoom stuck on loading"],
             6, 5, True),
            ("New starter device setup checklist",
             "1. Enrol the device with the organisation installer (carries the enrollment key).\n"
             "2. Confirm the agent heartbeat appears in Devices within 2 minutes.\n"
             "3. Assign the asset record to the user and send the acknowledgement email.\n"
             "4. Verify USB storage policy shows blocked.\n5. Confirm the patch baseline is current.",
             KnowledgeSource.MANUAL, None, None, 1, 0, True),
        ]
        for title, content, source, action_id, aliases, ok, bad, published in articles:
            vec = await embedder.embed(embedding_text(title, content, aliases), purpose="document")
            s.add(KnowledgeArticle(
                org_id=org.id, title=title, content=content, embedding=vec,
                embedding_model=embedder.name, source=source, action_id=action_id,
                symptom_samples=aliases,
                aliases_generated_at=ago(days=3) if aliases else None,
                successes=ok, failures=bad,
                created_by_user_id=admin.id if source is KnowledgeSource.MANUAL else None,
                published_at=ago(days=rng.randint(2, 60)) if published else None,
                created_at=ago(days=rng.randint(5, 150)),
            ))

        # ── Asset register ──────────────────────────────────────────────────
        user_pool = [admin, tech, tech2, *staff]
        for host, user, osv, model, cpu, ram_gb, disk_gb, mins, usb in FLEET:
            dev = devices[host]
            cat = AssetCategory.SERVER if host.startswith("TM-SRV") else (
                AssetCategory.DESKTOP if any(k in model for k in ("OptiPlex", "ThinkCentre"))
                else AssetCategory.LAPTOP)
            assignee = rng.choice(user_pool)
            s.add(Asset(
                org_id=org.id, asset_tag=f"TM-{host.split('-')[-1]}", name=f"{model} — {host}",
                category=cat, status=AssetStatus.IN_USE, device_id=dev.id,
                assigned_to_user_id=assignee.id, manufacturer=vendor_for(model), model=model,
                serial_number=dev.serial_number,
                location=rng.choice(["HQ — Detroit", "Plant 2 — Toledo", "Warehouse — Columbus", "Remote / Field"]),
                purchase_date=(NOW - timedelta(days=rng.randint(200, 900))).strftime("%Y-%m-%d"),
                warranty_expiry=(NOW + timedelta(days=rng.randint(-60, 800))).strftime("%Y-%m-%d"),
                purchase_cost=float(rng.choice([1180, 1340, 1490, 1720, 2150, 3400])),
                acknowledgement_status=rng.choice([
                    AcknowledgementStatus.ACKNOWLEDGED, AcknowledgementStatus.ACKNOWLEDGED,
                    AcknowledgementStatus.PENDING]),
                acknowledged_at=ago(days=rng.randint(5, 120)),
                created_at=ago(days=rng.randint(30, 300)),
            ))

        extras = [
            ("Dell UltraSharp U2723QE 27\"", AssetCategory.MONITOR, "Dell Inc.", 520, AssetStatus.IN_USE),
            ("Dell UltraSharp U2723QE 27\"", AssetCategory.MONITOR, "Dell Inc.", 520, AssetStatus.IN_USE),
            ("HP E24 G5 24\"", AssetCategory.MONITOR, "HP Inc.", 260, AssetStatus.IN_STORAGE),
            ("iPhone 15 (field sales)", AssetCategory.PHONE, "Apple", 890, AssetStatus.IN_USE),
            ("iPhone 15 (field sales)", AssetCategory.PHONE, "Apple", 890, AssetStatus.IN_USE),
            ("Samsung Galaxy Tab S9 (warehouse)", AssetCategory.TABLET, "Samsung", 740, AssetStatus.IN_USE),
            ("Zebra ZT411 label printer", AssetCategory.PERIPHERAL, "Zebra", 1650, AssetStatus.IN_USE),
            ("Cisco Catalyst 9200 switch", AssetCategory.NETWORK, "Cisco Systems", 3900, AssetStatus.IN_USE),
            ("Meraki MR46 access point", AssetCategory.NETWORK, "Cisco Meraki", 720, AssetStatus.IN_USE),
            ("Microsoft 365 E3 (100 seats)", AssetCategory.LICENSE, "Microsoft", 43200, AssetStatus.IN_USE),
            ("AutoCAD 2025 (12 seats)", AssetCategory.LICENSE, "Autodesk", 24600, AssetStatus.IN_USE),
            ("SAP GUI client licences", AssetCategory.LICENSE, "SAP SE", 9800, AssetStatus.IN_USE),
            ("Latitude 5440 (spare pool)", AssetCategory.LAPTOP, "Dell Inc.", 1180, AssetStatus.IN_STORAGE),
            ("Latitude 5440 (spare pool)", AssetCategory.LAPTOP, "Dell Inc.", 1180, AssetStatus.IN_STORAGE),
            ("EliteBook 840 G9 (screen fault)", AssetCategory.LAPTOP, "HP Inc.", 1420, AssetStatus.IN_REPAIR),
            ("ThinkPad T14 (end of life)", AssetCategory.LAPTOP, "Lenovo", 1290, AssetStatus.RETIRED),
            ("Surface Pro 8 (unreturned leaver)", AssetCategory.TABLET, "Microsoft", 1340, AssetStatus.LOST),
        ]
        for i, (name, cat, mfr, cost, status) in enumerate(extras):
            s.add(Asset(
                org_id=org.id, asset_tag=f"TM-A{2000 + i}", name=name, category=cat, status=status,
                manufacturer=mfr, purchase_cost=float(cost),
                assigned_to_user_id=rng.choice(user_pool).id if status == AssetStatus.IN_USE else None,
                location=rng.choice(["HQ — Detroit", "Plant 2 — Toledo", "Warehouse — Columbus"]),
                purchase_date=(NOW - timedelta(days=rng.randint(120, 1100))).strftime("%Y-%m-%d"),
                warranty_expiry=(NOW + timedelta(days=rng.randint(-200, 700))).strftime("%Y-%m-%d"),
                acknowledgement_status=AcknowledgementStatus.NOT_REQUIRED,
                created_at=ago(days=rng.randint(30, 400)),
            ))

        # ── Notifications ───────────────────────────────────────────────────
        notes = [
            (NotificationCategory.REMEDIATION, NotificationSeverity.WARNING,
             "Approval needed — Repair Microsoft Office",
             "TM-FIN-0151: Office has crashed 6 times in 24 hours. ASTRA proposes a quick repair.",
             "/self-healing", None, 0.3),
            (NotificationCategory.REMEDIATION, NotificationSeverity.CRITICAL,
             "Admin approval needed — remove restricted software",
             "TM-SAL-0407: uTorrent detected and matched to the restricted-software list.",
             "/self-healing", None, 3.6),
            (NotificationCategory.TELEMETRY, NotificationSeverity.CRITICAL,
             "Disk space critical on TM-OPS-0210",
             "C: dropped to 4.2 GB free (1.6%). Automatic cleanup ran and recovered 18.2 GB.",
             "/devices", ago(hours=2), 3.0),
            (NotificationCategory.TELEMETRY, NotificationSeverity.WARNING,
             "2 devices have not checked in",
             "TM-SAL-0407 (2 days) and TM-WH-0702 (4 days) are past the heartbeat threshold.",
             "/devices", None, 5.0),
            (NotificationCategory.REMEDIATION, NotificationSeverity.INFO,
             "15 issues resolved automatically today",
             "All automatic-tier actions completed and verified. No user tickets were raised.",
             "/self-healing", ago(hours=1), 6.0),
            (NotificationCategory.ASSET, NotificationSeverity.WARNING,
             "6 warranties expire within 60 days",
             "Review the asset register and start the replacement cycle.",
             "/assets", None, 22.0),
            (NotificationCategory.ASSET, NotificationSeverity.INFO,
             "Asset acknowledgement pending",
             "4 assigned devices are still awaiting the assignee's receipt confirmation.",
             "/assets", ago(days=1), 30.0),
            (NotificationCategory.SYSTEM, NotificationSeverity.INFO,
             "Agent 0.8.2 rolled out to 22 of 24 devices",
             "2 devices will update on their next check-in.",
             "/devices", ago(days=1), 40.0),
            (NotificationCategory.TELEMETRY, NotificationSeverity.WARNING,
             "Patch compliance below target",
             "3 devices are more than 30 days behind the patch baseline.",
             "/compliance", None, 48.0),
        ]
        for cat, sev, title, msg, link, read_at, hrs in notes:
            s.add(Notification(org_id=org.id, category=cat, severity=sev, title=title,
                               message=msg, link=link, read_at=read_at, created_at=ago(hours=hrs)))

        # ── Audit trail ─────────────────────────────────────────────────────
        audit = [
            (admin, "remediation.approve", "remediation_task", "Approved office_repair on TM-ENG-0303", 26),
            (admin, "remediation.approve", "remediation_task", "Approved driver_update on TM-EXE-0802", 51),
            (admin, "remediation.reject", "remediation_task", "Rejected reset_windows_update_components on TM-PLT-0603", 96),
            (tech, "remediation.create", "remediation_task", "Requested clear_temp on TM-ENG-0301", 0.05),
            (None, "device.enroll", "device", "TM-EXE-0802 enrolled with the organisation key", 120),
            (None, "device.enroll", "device", "TM-HR-0502 enrolled with the organisation key", 168),
            (admin, "user.create", "user", "Created technician account hana.suzuki@technomateai.com", 96 * 24),
            (admin, "settings.update", "organization_settings", "Minimum password length raised to 12", 200),
            (admin, "settings.update", "organization_settings", "Enrollment token lifetime set to 14 days", 202),
            (tech, "knowledge.create", "knowledge_article", "Added 'Print Spooler stops repeatedly (Event 7031)'", 300),
            (tech2, "asset.update", "asset", "Marked EliteBook 840 G9 as in repair", 74),
            (admin, "asset.assign", "asset", "Assigned TM-EXE-0801 to Eleanor Voss", 90),
            (admin, "compliance.policy_update", "organization", "Added uTorrent to restricted software", 340),
            (admin, "user.role_change", "user", "Marcus Webb promoted to technician", 400),
            (None, "agent.update", "device", "Agent auto-updated to 0.8.2 on 22 devices", 30),
            (admin, "auth.login", "user", "Signed in from 192.0.2.44 (Detroit, US)", 0.2),
            (tech, "auth.login", "user", "Signed in from 192.0.2.51 (Detroit, US)", 4),
            (admin, "report.export", "report", "Exported the fleet health report as CSV", 28),
            (admin, "device.deactivate", "device", "Retired ThinkPad T14 (end of life)", 480),
            (None, "remediation.execute", "remediation_task", "restart_outlook completed on TM-FIN-0142", 0.6),
        ]
        for actor, action, target, detail, hrs in audit:
            s.add(AuditLog(org_id=org.id, actor_id=actor.id if actor else None, action=action,
                           target_type=target, target_id=None, detail={"summary": detail},
                           created_at=ago(hours=hrs)))

        # ── AI conversations (the demo narrative) ───────────────────────────
        conv1 = Conversation(org_id=org.id, user_id=admin.id, device_id=devices["TM-FIN-0142"].id,
                             title="Outlook freezes when I open the archive mailbox",
                             created_at=ago(minutes=16))
        conv2 = Conversation(org_id=org.id, user_id=admin.id, device_id=devices["TM-OPS-0210"].id,
                             title="My laptop has become really slow", created_at=ago(hours=3))
        conv3 = Conversation(org_id=org.id, user_id=admin.id, device_id=devices["TM-FIN-0151"].id,
                             title="Word and Excel keep crashing", created_at=ago(minutes=20))
        conv4 = Conversation(org_id=org.id, user_id=admin.id, device_id=devices["TM-PLT-0603"].id,
                             title="Shop-floor printer still not printing", created_at=ago(hours=5))
        s.add_all([conv1, conv2, conv3, conv4])
        await s.flush()

        def msg(conv, role, content, trail=None, mins=0):
            return Message(conversation_id=conv.id, role=role, content=content,
                           tool_trail=trail, created_at=ago(minutes=mins))

        s.add_all([
            msg(conv1, MessageRole.USER,
                "Outlook freezes every time I open the archive mailbox. I have a board pack to send in 20 minutes.",
                None, 16),
            msg(conv1, MessageRole.ASSISTANT,
                "Let me look at the device before I change anything.\n\n"
                "**What I found on TM-FIN-0142**\n"
                "- RAM is at 93% (14.9 GB of 16 GB) — Outlook alone is holding 4.1 GB\n"
                "- Application log: Event 1002 (Application Hang) for OUTLOOK.EXE, 14 minutes ago\n"
                "- The archive OST is 18.4 GB, which is above the size where cached mode starts to stall\n"
                "- Knowledge base: this matches the runbook *Outlook freezes when opening a large mailbox*\n\n"
                "This is memory pressure, not a corrupt mailbox. The documented fix is to restart "
                "Outlook — an **automatic-tier** action, so I can run it now without waiting for approval. "
                "Nothing is deleted and your drafts are preserved.\n\nShall I go ahead?",
                [{"tool": "get_device_telemetry", "result": "cpu 34% · ram 93% (14.9/16 GB) · C: 212 GB free"},
                 {"tool": "get_event_logs", "result": "Event 1002 Application Hang — OUTLOOK.EXE (14 min ago)"},
                 {"tool": "get_installed_apps", "result": "Microsoft 365 Apps 16.0.18324.20168"},
                 {"tool": "search_knowledge", "result": "Matched: 'Outlook freezes when opening a large mailbox' (0.71)"}],
                15),
            msg(conv1, MessageRole.USER, "Yes please, go ahead.", None, 14),
            msg(conv1, MessageRole.ASSISTANT,
                "Running **Restart Outlook** on TM-FIN-0142 now.",
                [{"tool": "execute_remediation", "result": "restart_outlook · automatic tier · dispatched to agent"}],
                14),
            msg(conv1, MessageRole.ASSISTANT,
                "✅ **Done — and verified.**\n\n"
                "- Outlook restarted at 09:41 and reopened with your drafts intact\n"
                "- RAM is now at 61% (9.8 GB of 16 GB) — 5.1 GB returned\n"
                "- The archive mailbox opened in 4 seconds with no hang event since\n\n"
                "To stop it recurring, I can set the cached-mail slider on the archive account to 3 months. "
                "That is a change to your Outlook profile, so I will only do it if you ask.\n\n"
                "This action and its result are recorded in the audit log.",
                [{"tool": "get_device_telemetry", "result": "cpu 18% · ram 61% (9.8/16 GB) — post-fix verification"},
                 {"tool": "get_event_logs", "result": "No hang events since 09:41"}],
                13),

            msg(conv2, MessageRole.USER, "My laptop has become really slow since yesterday.", None, 185),
            msg(conv2, MessageRole.ASSISTANT,
                "Checked TM-OPS-0210.\n\n"
                "**Evidence**\n- C: has 4.2 GB free of 256 GB (1.6%) — below the 10% policy floor\n"
                "- Windows is paging heavily as a result; CPU is normal at 22%\n"
                "- Event 51 (paging operation error) appeared twice overnight\n"
                "- 3 Windows updates cannot download because there is no space\n\n"
                "This is disk exhaustion, not a hardware fault. I will run two automatic-tier cleanups: "
                "temp files in your session, then the machine-wide caches. Both rebuild themselves and "
                "no documents are touched.",
                [{"tool": "get_device_telemetry", "result": "cpu 22% · ram 54% · C: 4.2/256 GB free (1.6%)"},
                 {"tool": "get_event_logs", "result": "Event 51 ×2 — paging operation error"},
                 {"tool": "get_windows_updates", "result": "3 pending, download blocked (insufficient space)"}],
                184),
            msg(conv2, MessageRole.ASSISTANT,
                "✅ **Recovered 18.2 GB.**\n\n"
                "- clear_temp: 11.8 GB of user temp files\n- clear_system_temp: 6.4 GB from Windows Temp, "
                "Prefetch and the Update cache\n- C: now has 22.4 GB free (8.8%)\n\n"
                "Still slightly under the 10% floor because this device only has a 256 GB drive. I have "
                "raised a note on the asset record recommending a replacement in the next refresh cycle. "
                "The 3 blocked updates will now download on the next cycle.",
                [{"tool": "execute_remediation", "result": "clear_temp · automatic · +11.8 GB"},
                 {"tool": "execute_remediation", "result": "clear_system_temp · automatic · +6.4 GB"},
                 {"tool": "get_device_telemetry", "result": "C: 22.4/256 GB free (8.8%) — verified"}],
                182),

            msg(conv3, MessageRole.USER, "Word and Excel keep crashing on me all morning.", None, 20),
            msg(conv3, MessageRole.ASSISTANT,
                "Checked TM-FIN-0151.\n\n**Evidence**\n"
                "- 6 crashes in 24 hours: Event 1000, faulting module VBE7.DLL\n"
                "- Both Word and Excel are affected, so this is the shared Office VBA component, not one file\n"
                "- RAM and disk are healthy (48% and 214 GB free), so resources are not the cause\n"
                "- Knowledge base match: an Office quick repair is the documented fix\n\n"
                "An Office repair is **approval-required tier** — it closes all Office apps for about "
                "10 minutes, so I cannot run it on my own. I have sent the request to your IT team with "
                "this evidence attached; you will see it complete here once approved.\n\n"
                "In the meantime, save your work in Excel every few minutes — the crash happens on open, "
                "not on save.",
                [{"tool": "get_event_logs", "result": "Event 1000 ×6 — faulting module VBE7.DLL (Word, Excel)"},
                 {"tool": "get_device_telemetry", "result": "cpu 19% · ram 48% · C: 214 GB free"},
                 {"tool": "search_knowledge", "result": "Matched: Office repair runbook (0.66)"},
                 {"tool": "request_approval", "result": "office_repair · approval_required · queued for IT"}],
                19),
            msg(conv4, MessageRole.USER,
                "The shop-floor printer still isn't printing. I've already restarted my machine twice.",
                None, 300),
            msg(conv4, MessageRole.ASSISTANT,
                "Checked TM-PLT-0603.\n\n**Evidence**\n"
                "- Print Spooler is stopped — Event 7031, three times today\n"
                "- 14 jobs are sitting in the queue\n"
                "- Knowledge base: this matches your runbook for repeated spooler stops\n\n"
                "Restarting the spooler is automatic tier, so I am running it now.",
                [{"tool": "get_event_logs", "result": "Event 7031 x3 - Print Spooler terminated unexpectedly"},
                 {"tool": "get_services", "result": "Spooler: Stopped (start type Automatic)"},
                 {"tool": "search_knowledge", "result": "Matched: 'Print Spooler stops repeatedly (Event 7031)' (0.68)"},
                 {"tool": "execute_remediation", "result": "restart_service:Spooler - automatic - spooler running"}],
                299),
            msg(conv4, MessageRole.ASSISTANT,
                "Spooler restarted and it has stayed running. Please try printing again.",
                None, 298),
            msg(conv4, MessageRole.USER, "Still nothing. Same error on the screen.", None, 296),
            msg(conv4, MessageRole.ASSISTANT,
                "Then it is not the spooler. The queue is clearing and the service is healthy, "
                "but the driver reports the device itself as offline — that is the printer or its "
                "network path, and I cannot reach either from this machine.\n\n"
                "**Shall I raise a ticket with your IT helpdesk?** I will attach everything I have "
                "already checked, so nobody has to ask you these questions again.",
                [{"tool": "get_services", "result": "Spooler: Running - queue drained, 0 jobs held"},
                 {"tool": "offer_support_ticket", "result": "escalation offered - awaiting the user's answer"}],
                295),
            msg(conv4, MessageRole.USER, "Haan, kar do.", None, 294),
            msg(conv4, MessageRole.ASSISTANT,
                "✅ **Ticket INC-4821 raised** in your Freshservice.\n\n"
                "- Queue: Endpoint Support · Priority: Medium\n"
                "- Category: Hardware / Printing (mapped from the action I attempted)\n"
                "- Attached: the device, its telemetry, the event log entries, the fix I tried "
                "and what it changed\n\n"
                "You will get the usual email from the helpdesk. If you report this again today "
                "I will point you back to INC-4821 rather than open a second ticket.",
                [{"tool": "raise_support_ticket", "result": "freshservice - INC-4821 - consent recorded, dossier attached"}],
                293),
        ])

        # ── Escalations: what ASTRA handed to a human ───────────────────────
        s.add_all([
            SupportEscalation(
                org_id=org.id, conversation_id=conv4.id, device_id=devices["TM-PLT-0603"].id,
                user_id=admin.id,
                problem_summary="The shop-floor printer still isn't printing. I've already "
                                "restarted my machine twice.",
                action_id="restart_service", state=EscalationState.RAISED,
                provider="freshservice", external_ticket_id="INC-4821",
                external_url="https://technomate.freshservice.com/a/tickets/4821",
                raised_at=ago(minutes=293), created_at=ago(minutes=295),
            ),
            SupportEscalation(
                org_id=org.id, device_id=devices["TM-WH-0702"].id,
                problem_summary="Warehouse scanner station has had no network for four days.",
                action_id="restart_network_adapter", state=EscalationState.RAISED,
                provider="freshservice", external_ticket_id="INC-4803",
                external_url="https://technomate.freshservice.com/a/tickets/4803",
                raised_at=ago(hours=70), created_at=ago(hours=71),
            ),
            SupportEscalation(
                org_id=org.id, device_id=devices["TM-EXE-0802"].id, user_id=admin.id,
                problem_summary="Second monitor flickers when docked.",
                action_id="driver_update", state=EscalationState.DECLINED,
                created_at=ago(hours=52),
            ),
        ])

        await s.commit()

    print(f"Seeded '{ORG_NAME}': {len(FLEET)} devices, 4 conversations, "
          f"{len(auto_history) + len(pending) + len(approved_done) + 3} remediations.")
    # Job logs are retained; the production password is the operator's, not the log's.
    print(f"Sign in: {ADMIN_EMAIL} / {ADMIN_PASSWORD if LOCAL else '(ASTRA_DEMO_PASSWORD)'}")


if __name__ == "__main__":
    asyncio.run(main())
