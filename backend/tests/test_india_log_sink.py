"""Z1 — the India log sink's legal floor lives in a shell script, so pin it here.

Someone trimming log costs by lowering RETENTION_DAYS, or "tidying" the region, would
otherwise drop below what CERT-In and the DPDP Rules require without any test noticing.
"""
import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "logging" / "india-log-sink.sh"


def _value(name: str) -> str:
    m = re.search(rf'^{name}="?([^"\n]+)"?$', SCRIPT.read_text(encoding="utf-8"), re.M)
    assert m, f"{name} not found in {SCRIPT}"
    return m.group(1)


def test_logs_stay_in_india_for_at_least_a_year():
    assert _value("LOCATION") == "asia-south1"            # Mumbai — within India (CERT-In)
    assert int(_value("RETENTION_DAYS")) >= 365           # DPDP Rules: processing logs >= 1 year


def test_sink_copies_everything():
    # A narrower filter would quietly leave some service's logs outside India.
    assert _value("FILTER").strip("'") == "severity>=DEFAULT"
