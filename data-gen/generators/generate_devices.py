"""
Generate one-to-three trusted devices per customer, plus a small pool of
untrusted "attacker" devices never linked to any customer's normal history
(useful later for injecting new-device / account-takeover scenarios).

Requires customers.json to already exist (run generate_customers.py first).

Usage: python3 generate_devices.py [--seed 1337]
"""

from __future__ import annotations

import argparse
import datetime as dt

from .common import DEVICE_OS, DEVICE_TYPES, load_json, new_id, rng, write_json


def make_device(customer_id: str | None, r, trusted: bool = True) -> dict[str, object]:
    device_type = r.choice(DEVICE_TYPES)
    return {
        "device_id": new_id("dev", r),
        "customer_id": customer_id,
        "device_type": device_type,
        "os": r.choice(DEVICE_OS[device_type]),
        "first_seen": (dt.date.today() - dt.timedelta(days=r.randint(1, 900))).isoformat(),
        "trusted": trusted,
    }


def generate(seed: int) -> list[dict[str, object]]:
    r = rng(seed)
    customers = load_json("customers.json")
    devices: list[dict[str, object]] = []

    for customer in customers:
        for _ in range(r.choice([1, 1, 2, 3])):
            devices.append(make_device(customer["customer_id"], r, trusted=True))

    # Untrusted device pool, not tied to any customer's normal history.
    # Producers can pick from these to simulate a new/unusual device login.
    for _ in range(max(20, len(customers) // 5)):
        devices.append(make_device(customer_id=None, r=r, trusted=False))

    return devices


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    devices = generate(args.seed)
    path = write_json("devices.json", devices)
    print(f"Wrote {len(devices)} devices to {path}")


if __name__ == "__main__":
    main()
