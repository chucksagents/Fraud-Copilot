"""
Generate a pool of synthetic merchants with category and risk info.
Writes data-gen/fixtures/merchants.json.

Usage: python3 generate_merchants.py [--count 60] [--seed 1337]
"""

from __future__ import annotations

import argparse
from typing import Any

from .common import (
    CITIES,
    MERCHANT_CATEGORIES,
    MERCHANT_NAME_STEMS,
    new_id,
    rng,
    write_json,
)

CATEGORY_SUFFIX = {
    "grocery": "Market",
    "restaurant": "Kitchen",
    "gas_station": "Fuel",
    "electronics": "Electronics",
    "travel": "Travel",
    "online_retail": "Online",
    "utilities": "Utilities",
    "entertainment": "Entertainment",
    "pharmacy": "Pharmacy",
    "home_improvement": "Home & Hardware",
    "clothing": "Apparel",
    "subscription": "Digital Services",
}

# A handful of categories/merchants are deliberately marked higher risk so
# rules and agent narratives have something concrete to point at.
HIGH_RISK_CATEGORIES = {"online_retail", "subscription", "entertainment"}


def make_merchant(r) -> dict[str, Any]:
    category = r.choice(MERCHANT_CATEGORIES)
    stem = r.choice(MERCHANT_NAME_STEMS)
    city, country, _, _ = r.choice(CITIES)
    risk_level = "low"
    if category in HIGH_RISK_CATEGORIES:
        risk_level = r.choice(["medium", "medium", "high"])
    else:
        risk_level = r.choice(["low", "low", "low", "medium"])
    return {
        "merchant_id": new_id("merch", r),
        "name": f"{stem} {CATEGORY_SUFFIX[category]}",
        "category": category,
        "risk_level": risk_level,
        "country": country,
    }


def generate(count: int, seed: int) -> list[dict[str, Any]]:
    r = rng(seed)
    return [make_merchant(r) for _ in range(count)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    merchants = generate(args.count, args.seed)
    path = write_json("merchants.json", merchants)
    print(f"Wrote {len(merchants)} merchants to {path}")


if __name__ == "__main__":
    main()
