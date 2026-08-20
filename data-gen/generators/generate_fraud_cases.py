"""
Generate a small history of previously resolved fraud cases per a subset of
customers. This gives the investigation/policy agents something to
reference as precedent ("similar cases were resolved as...") and gives the
customer-context API a non-empty case history endpoint to serve.

Requires customers.json to already exist.

Usage: python3 generate_fraud_cases.py [--count 40] [--seed 1337]
"""

from __future__ import annotations
from typing import Any

import argparse
import datetime as dt

from .common import load_json, new_id, rng, write_json

RULES = [
    "high_velocity",
    "multiple_failed_logins",
    "new_or_unusual_device",
    "impossible_travel",
    "amount_anomaly",
]

OUTCOMES = [
    ("card_lock", "confirmed_fraud"),
    ("contact_customer", "false_positive"),
    ("no_action", "false_positive"),
    ("escalate", "confirmed_fraud"),
]

SUMMARY_TEMPLATES = {
    "high_velocity": "Customer had {n} transactions within {mins} minutes; pattern matched card-testing behavior.",
    "multiple_failed_logins": "{n} failed login attempts before a successful login from a new device.",
    "new_or_unusual_device": "Login and subsequent transaction from a device never seen before on this account.",
    "impossible_travel": "Two logins {mins} minutes apart from locations that are not physically reachable in that time.",
    "amount_anomaly": "Transaction amount was {mult}x the customer's typical spend for that merchant category.",
}


def make_case(customer_id: str, r) -> dict[str, Any]:
    rule = r.choice(RULES)
    action_type, outcome = r.choice(OUTCOMES)
    generated_at = dt.datetime.utcnow() - dt.timedelta(days=r.randint(5, 400))
    summary = SUMMARY_TEMPLATES[rule].format(
        n=r.randint(3, 9), mins=r.randint(2, 45), mult=round(r.uniform(3, 12), 1)
    )
    return {
        "case_id": new_id("case", r),
        "alert_id": new_id("alert", r),
        "customer_id": customer_id,
        "rule_triggered": rule,
        "action_type": action_type,
        "status": "executed" if outcome == "confirmed_fraud" else "rejected",
        "outcome": outcome,
        "resolved_at": generated_at.isoformat() + "Z",
        "summary": summary,
    }


def generate(count: int, seed: int) -> list[dict[str, Any]]:
    r = rng(seed)
    customers = load_json("customers.json")
    sampled_customers = r.sample(customers, k=min(count, len(customers)))
    return [make_case(c["customer_id"], r) for c in sampled_customers]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    cases = generate(args.count, args.seed)
    path = write_json("fraud_cases_history.json", cases)
    print(f"Wrote {len(cases)} historical fraud cases to {path}")


if __name__ == "__main__":
    main()
