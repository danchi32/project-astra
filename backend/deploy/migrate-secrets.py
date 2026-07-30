#!/usr/bin/env python3
"""Copy the backend's secret env values from Railway into Google Secret Manager.

Values are read from `railway variables --json` and piped straight into gcloud on stdin —
they are never printed, logged, or written to disk. Only names and status are shown.

ASTRA_DATABASE_URL is deliberately NOT taken from Railway (that's the old Railway
Postgres). Pass the Neon URL instead:

    NEON_DATABASE_URL='postgresql+asyncpg://...-pooler.../neondb?ssl=require' \
    python deploy/migrate-secrets.py

Prereqs: `railway` linked + logged in, `gcloud` authed with the target project set.
Set GCLOUD=/full/path/to/gcloud if it isn't on PATH.
"""
import json
import os
import shutil
import subprocess
import sys

GCLOUD = os.environ.get("GCLOUD") or shutil.which("gcloud") or "gcloud"


def _argv(exe: str, *args: str) -> list[str]:
    """Windows can't CreateProcess a .cmd/.bat directly (both gcloud and railway ship as
    .cmd there), so route those through cmd.exe. Values are passed on stdin, never argv."""
    resolved = shutil.which(exe) or exe
    if os.name == "nt" and resolved.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", resolved, *args]
    return [resolved, *args]

# Secret values that must live in Secret Manager (never in the service config).
SECRET_VARS = [
    "ASTRA_JWT_SECRET_KEY",
    "ASTRA_ANTHROPIC_API_KEY",
    "ASTRA_RESEND_API_KEY",
    "ASTRA_PAYPAL_CLIENT_ID",
    "ASTRA_PAYPAL_CLIENT_SECRET",
    "ASTRA_PAYPAL_PLAN_ID",
    "ASTRA_PAYPAL_WEBHOOK_ID",
    "ASTRA_BOOTSTRAP_ADMIN_EMAIL",
    "ASTRA_BOOTSTRAP_ADMIN_PASSWORD",
    "ASTRA_EMAIL_FROM",
]


def gcloud(*args: str, stdin_value: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        _argv(GCLOUD, *args),
        input=stdin_value,
        capture_output=True,
        text=True,
    )


def secret_exists(name: str) -> bool:
    return gcloud("secrets", "describe", name, "--format=value(name)").returncode == 0


def upsert(name: str, value: str) -> str:
    """Create the secret, or add a new version if it already exists. Returns a status word."""
    if secret_exists(name):
        r = gcloud("secrets", "versions", "add", name, "--data-file=-", stdin_value=value)
        return "new version" if r.returncode == 0 else f"FAILED ({r.stderr.strip().splitlines()[-1:]})"
    r = gcloud(
        "secrets", "create", name,
        "--replication-policy=automatic", "--data-file=-",
        stdin_value=value,
    )
    return "created" if r.returncode == 0 else f"FAILED ({r.stderr.strip().splitlines()[-1:]})"


def main() -> int:
    raw = subprocess.run(
        _argv("railway", "variables", "--json"), capture_output=True, text=True
    )
    if raw.returncode != 0:
        print("Could not read Railway variables. Is this directory linked (`railway status`)?")
        print(raw.stderr.strip()[:400])
        return 1
    try:
        railway_vars = json.loads(raw.stdout)
    except json.JSONDecodeError as exc:
        print(f"Railway returned output that isn't JSON: {exc}")
        return 1

    todo: list[tuple[str, str]] = []

    # The database URL comes from Neon, not Railway.
    neon = os.environ.get("NEON_DATABASE_URL", "").strip()
    if neon:
        if not neon.startswith("postgresql+asyncpg://"):
            print("NEON_DATABASE_URL must start with postgresql+asyncpg:// (async driver).")
            return 1
        todo.append(("ASTRA_DATABASE_URL", neon))
    else:
        print("! NEON_DATABASE_URL not set — skipping ASTRA_DATABASE_URL")

    for name in SECRET_VARS:
        value = (railway_vars.get(name) or "").strip()
        if value:
            todo.append((name, value))
        else:
            print(f"- {name}: not set on Railway, skipping")

    print(f"\nWriting {len(todo)} secret(s) to Secret Manager via {GCLOUD}\n")
    failures = 0
    for name, value in todo:
        status = upsert(name, value)
        if "FAILED" in status:
            failures += 1
        print(f"  {name}: {status}")

    print("\nDone." if not failures else f"\n{failures} secret(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
