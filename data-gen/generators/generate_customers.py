"""
Generate synthetic customers, each with one or two accounts and one or two
cards per account. Writes data-gen/fixtures/customers.json.

Usage: python3 generate_customers.py [--count 200] [--seed 1337]
"""
from __future__ import annotations
from typing import Any

import argparse
import datetime as dt

from .common import CITIES, FIRST_NAMES, LAST_NAMES, new_id, rng, write_json

ACCOUNT_TYPES = ["checking", "credit"]
CARD_TYPES = {"checking": "debit", "credit": "credit"}
RISK_TIERS = ["low", "low", "low", "medium", "medium", "high"]  # weighted


def make_card(account_type: str, r) -> dict[str, Any]:
    return {
        "card_id": new_id("card", r),
        "card_type": CARD_TYPES[account_type],
        "last4": f"{r.randint(0, 9999):04d}",
        "issued_at": (dt.date.today() - dt.timedelta(days=r.randint(30, 1800))).isoformat(),
    }


def make_account(r) -> dict[str, Any]:
    account_type = r.choice(ACCOUNT_TYPES)
    num_cards = r.choice([1, 1, 2])
    return {
        "account_id": new_id("acct", r),
        "account_type": account_type,
        "opened_at": (dt.date.today() - dt.timedelta(days=r.randint(90, 3650))).isoformat(),
        "cards": [make_card(account_type, r) for _ in range(num_cards)],
    }


def make_customer(r) -> dict[str, Any]:
    first = r.choice(FIRST_NAMES)
    last = r.choice(LAST_NAMES)
    city, country, lat, lon = r.choice(CITIES)
    num_accounts = r.choice([1, 1, 2])
    return {
        "customer_id": new_id("cust", r),
        "name": f"{first} {last}",
        "email": f"{first.lower()}.{last.lower()}{r.randint(1,999)}@example.com",
        "phone": f"+1{r.randint(2000000000, 9999999999)}",
        "risk_tier": r.choice(RISK_TIERS),
        "home_location": {"city": city, "country": country, "lat": lat, "lon": lon},
        "accounts": [make_account(r) for _ in range(num_accounts)],
    }


def generate(count: int, seed: int) -> list[dict[str, Any]]:
    r = rng(seed)
    return [make_customer(r) for _ in range(count)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    customers = generate(args.count, args.seed)
    path = write_json("customers.json", customers)
    print(f"Wrote {len(customers)} customers to {path}")


if __name__ == "__main__":
    main()
