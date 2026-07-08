"""CWD-independent demo launcher: sets demo env + starts uvicorn on port 8000.

Used by .claude/launch.json so the backend runs the same regardless of the
directory the preview system launches it from. Local demo only — never prod.
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

DB_PATH = os.path.join(BACKEND_DIR, "astra-demo.db").replace("\\", "/")
os.environ.setdefault("ASTRA_DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH}")
os.environ.setdefault("ASTRA_JWT_SECRET_KEY", "demo-secret-key-local-only-not-for-prod")

import uvicorn  # noqa: E402  (import after sys.path/env setup)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="info")
