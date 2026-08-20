"""
Generate a per-customer "normal behavior" profile: typical spend amount,
typical merchant categories, typical channel, typical countries, typical
login hours. This is what producers sample from for baseline traffic, and
what an amount/velocity/location rule (and the investigation agent) treats
as the customer's baseline.

Requires customers.json and merchants.json to already exist.

Usage: python3 generate_customer_behavior.py [--seed 1337]
"""

from __future__ import annotations

import argparse
from typing import Any

from .common import MERCHANT_CATEGORIES, load_json, rng, write_json


def make_profile(customer: dict[str, Any], r) -> dict[str, Any]:
    home_country = customer["home_location"]["country"]
    avg_amount = round(r.uniform(20, 250), 2)
    return {
        "customer_id": customer["customer_id"],
        "avg_transaction_amount": avg_amount,
        "stddev_transaction_amount": round(avg_amount * r.uniform(0.2, 0.5), 2),
        "typical_merchant_categories": r.sample(
            MERCHANT_CATEGORIES, k=r.randint(3, 5)
        ),
        "typical_channels": r.choice([
            ["card_present", "online"],
            ["card_present"],
            ["online"],
        ]),
        "typical_countries": [home_country],
        "typical_login_hours_local": sorted(r.sample(range(6, 23), k=r.randint(4, 8))),
        "avg_daily_transaction_count": round(r.uniform(0.5, 4.0), 1),
    }


def generate(seed: int) -> list[dict[str, Any]]:
    r = rng(seed)
    customers = load_json("customers.json")
    return [make_profile(c, r) for c in customers]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    profiles = generate(args.seed)
    path = write_json("customer_behavior.json", profiles)
    print(f"Wrote {len(profiles)} behavior profiles to {path}")


if __name__ == "__main__":
    main()
