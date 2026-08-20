"""
Run every generator in dependency order and (re)write the full fixture set
under data-gen/fixtures/.

Usage: python3 generate_all.py [--seed 1337] [--customers 200] [--merchants 60] [--fraud-cases 40]
"""

from __future__ import annotations

import argparse

from . import generate_customer_behavior
from . import generate_customers
from . import generate_devices
from . import generate_fraud_cases
from . import generate_merchants
from . import generate_policy_docs
from .common import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--customers", type=int, default=200)
    parser.add_argument("--merchants", type=int, default=60)
    parser.add_argument("--fraud-cases", type=int, default=40)
    args = parser.parse_args()

    customers = generate_customers.generate(args.customers, args.seed)
    write_json("customers.json", customers)
    print(f"customers.json: {len(customers)} customers")

    devices = generate_devices.generate(args.seed)
    write_json("devices.json", devices)
    print(f"devices.json: {len(devices)} devices")

    merchants = generate_merchants.generate(args.merchants, args.seed)
    write_json("merchants.json", merchants)
    print(f"merchants.json: {len(merchants)} merchants")

    behavior = generate_customer_behavior.generate(args.seed)
    write_json("customer_behavior.json", behavior)
    print(f"customer_behavior.json: {len(behavior)} profiles")

    fraud_cases = generate_fraud_cases.generate(args.fraud_cases, args.seed)
    write_json("fraud_cases_history.json", fraud_cases)
    print(f"fraud_cases_history.json: {len(fraud_cases)} cases")

    generate_policy_docs.main()

    print("\nAll fixtures generated under data-gen/fixtures/")


if __name__ == "__main__":
    main()
