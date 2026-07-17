"""Create a PayPal Product + per-seat subscription Plan and print the Plan ID.

PayPal has no dashboard UI for subscription plans — they exist only via the API —
so run this once to get the `P-...` id for ASTRA_PAYPAL_PLAN_ID.

Needs only the PayPal credentials in the environment (no database):
    ASTRA_PAYPAL_CLIENT_ID, ASTRA_PAYPAL_CLIENT_SECRET

Run it in the Railway backend Shell (those vars are already there), or locally
with them exported:

    python scripts/create_paypal_plan.py --amount 10 --currency USD --live
    python scripts/create_paypal_plan.py --amount 10 --interval MONTH   # sandbox

Targets LIVE with --live (or ASTRA_PAYPAL_SANDBOX=false), else sandbox. The plan is
per-UNIT with quantity enabled, so a subscription for N device licenses is charged
amount * N. Creating a plan does NOT charge anyone.
"""
import argparse
import os
import sys

import httpx

CLIENT_ID = os.getenv("ASTRA_PAYPAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("ASTRA_PAYPAL_CLIENT_SECRET")


def _is_live(force_live: bool, force_sandbox: bool) -> bool:
    if force_live:
        return True
    if force_sandbox:
        return False
    return os.getenv("ASTRA_PAYPAL_SANDBOX", "true").strip().lower() in ("false", "0", "no")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--amount", required=True, help="Price per device per cycle, e.g. 10 or 10.00")
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--interval", default="MONTH", choices=["DAY", "WEEK", "MONTH", "YEAR"])
    ap.add_argument("--interval-count", type=int, default=1)
    ap.add_argument("--name", default="ASTRA per device")
    ap.add_argument("--live", action="store_true", help="Force PayPal LIVE")
    ap.add_argument("--sandbox", action="store_true", help="Force PayPal SANDBOX")
    args = ap.parse_args()

    if not (CLIENT_ID and CLIENT_SECRET):
        sys.exit("Set ASTRA_PAYPAL_CLIENT_ID and ASTRA_PAYPAL_CLIENT_SECRET first.")

    live = _is_live(args.live, args.sandbox)
    base = "https://api-m.paypal.com" if live else "https://api-m.sandbox.paypal.com"
    print(f"Target: {'LIVE' if live else 'SANDBOX'}  ({base})")

    with httpx.Client(timeout=30) as client:
        tok = client.post(
            f"{base}/v1/oauth2/token",
            auth=(CLIENT_ID, CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if tok.status_code >= 400:
            sys.exit(f"PayPal auth failed ({tok.status_code}): {tok.text}")
        headers = {"Authorization": f"Bearer {tok.json()['access_token']}", "Content-Type": "application/json"}

        prod = client.post(
            f"{base}/v1/catalogs/products",
            headers=headers,
            json={"name": "ASTRA", "type": "SERVICE", "category": "SOFTWARE"},
        )
        prod.raise_for_status()
        product_id = prod.json()["id"]
        print(f"Product created: {product_id}")

        amount = f"{float(args.amount):.2f}"
        plan = client.post(
            f"{base}/v1/billing/plans",
            headers=headers,
            json={
                "product_id": product_id,
                "name": args.name,
                "status": "ACTIVE",
                "quantity_supported": True,
                "billing_cycles": [{
                    "frequency": {"interval_unit": args.interval, "interval_count": args.interval_count},
                    "tenure_type": "REGULAR",
                    "sequence": 1,
                    "total_cycles": 0,  # renew forever
                    "pricing_scheme": {"fixed_price": {"value": amount, "currency_code": args.currency}},
                }],
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "setup_fee_failure_action": "CONTINUE",
                    "payment_failure_threshold": 2,
                },
            },
        )
        if plan.status_code >= 400:
            sys.exit(f"Plan creation failed ({plan.status_code}): {plan.text}")
        plan_id = plan.json()["id"]

    print("\n" + "=" * 60)
    print(f"PLAN CREATED  ->  {plan_id}")
    print(f"  price: {amount} {args.currency} per device / {args.interval_count} {args.interval}")
    print("=" * 60)
    print("\nSet this in Railway, then Deploy:")
    print(f"  ASTRA_PAYPAL_PLAN_ID = {plan_id}")


if __name__ == "__main__":
    main()
