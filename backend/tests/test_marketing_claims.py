"""The marketing claim file must match the shipped remediation registry.

This test lives in the backend, not in the marketing service, because it has to run when
the *registry* changes. That is the moment the claim file goes stale, and it is a moment
nobody is thinking about marketing copy — someone adds an action, ships it, and a document
in another directory quietly starts describing a product that no longer exists.

It is not hypothetical. `marketing/creative/astra-image-prompt-master.md` was written on
2026-08-22 against the code and was wrong by 2026-08-29: `logoff_session` and
`reset_local_password` had shipped and were never added to its admin-only list. A prose
document cannot defend itself. This one can.

The comparison is exact in both directions. A claimed action that no longer exists is an
obvious problem; a shipped action missing from the file is the subtler one, because it
reads as an omission rather than an error — and it means marketing is describing an older,
smaller product than the one customers are buying.
"""
import pathlib

import pytest
import yaml

from app.services.remediation.actions import _ACTIONS

# Imported normally rather than via importorskip: a check that can silently disable
# itself when a dependency goes missing is not a check. pyyaml is in requirements-dev.

CLAIMS_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / "marketing-service" / "brand" / "claims.yaml"
)


@pytest.fixture(scope="module")
def claims() -> dict:
    if not CLAIMS_PATH.exists():
        pytest.skip(f"{CLAIMS_PATH} not present")
    return yaml.safe_load(CLAIMS_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("tier", ["automatic", "approval_required", "admin_only"])
def test_claimed_actions_match_the_registry(claims: dict, tier: str) -> None:
    registry = {a.id for a in _ACTIONS if a.tier.value == tier}
    claimed = set(claims["actions"][tier])

    missing = registry - claimed
    invented = claimed - registry
    assert not missing, (
        f"{tier}: shipped but not in claims.yaml: {sorted(missing)}. "
        "Marketing is describing a smaller product than the one being sold."
    )
    assert not invented, (
        f"{tier}: claimed but not shipped: {sorted(invented)}. "
        "This is a false capability claim."
    )


def test_no_action_is_claimed_under_two_tiers(claims: dict) -> None:
    """The tier IS the promise. An action listed twice makes the promise meaningless."""
    tiers = ["automatic", "approval_required", "admin_only"]
    seen: dict[str, str] = {}
    for tier in tiers:
        for action_id in claims["actions"][tier]:
            assert action_id not in seen, (
                f"{action_id} is claimed under both {seen[action_id]} and {tier}"
            )
            seen[action_id] = tier


def test_actions_withheld_from_the_model_are_listed_as_such(claims: dict) -> None:
    """`operator_only` actions act on a person, not a fault.

    Copy that describes ASTRA deciding to lock a screen or message a user is wrong about
    the product and, worse, describes a phishing primitive as a feature.
    """
    registry = {a.id for a in _ACTIONS if a.operator_only}
    claimed = set(claims["actions"]["withheld_from_ai"])

    assert claimed == registry, (
        f"withheld_from_ai is {sorted(claimed)} but the registry withholds "
        f"{sorted(registry)}. These must not drift: the difference is between "
        "'a human asked for this' and 'the AI decided to interrupt someone'."
    )


def test_every_forbidden_claim_states_the_reality(claims: dict) -> None:
    """A prohibition without the true version invites someone to re-invent the false one."""
    for entry in claims["forbidden"]:
        assert entry.get("never_claim"), f"{entry.get('id')} has no never_claim"
        assert entry.get("reality"), (
            f"{entry['id']} says what not to claim but not what is true instead"
        )


def test_removed_actions_stay_forbidden(claims: dict) -> None:
    """`registry_fix` and `driver_update` were removed because the agent never had them.

    They appeared in early copy, so the file must keep saying they are unavailable rather
    than merely stop mentioning them.
    """
    registry = {a.id for a in _ACTIONS}
    assert "registry_fix" not in registry
    assert "driver_update" not in registry

    forbidden_text = " ".join(
        f"{e.get('never_claim', '')} {e.get('reality', '')}" for e in claims["forbidden"]
    ).lower()
    assert "registry" in forbidden_text
    assert "driver" in forbidden_text
