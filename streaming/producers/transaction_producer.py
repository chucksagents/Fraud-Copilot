"""
Emit synthetic `transactions` events, validated against
docs/schemas/transaction.schema.json.

Most events follow the customer's normal behavior profile
(data-gen/fixtures/customer_behavior.json). A configurable fraction are
deliberately anomalous — either a single amount spike, or a short burst of
rapid transactions on one card — so the Flink rules built later have
something to fire on.

Usage:
  python3 transaction_producer.py --sink stdout --count 50
  python3 transaction_producer.py --sink file --count 500
  python3 transaction_producer.py --sink kafka --count 1000 --rate 5

Run `python3 data-gen/generators/generate_all.py` first if fixtures don't
exist yet.
"""

from __future__ import annotations

import argparse
import datetime as dt
import random
import time
from typing import Any
import uuid

try:
    from .common import Sink, load_fixture, load_schema, validate_event
except ImportError:
    from common import Sink, load_fixture, load_schema, validate_event

TRANSACTION_SCHEMA = load_schema("transaction.schema.json")


def _pick_card(customer: dict[str, Any], r: random.Random) -> tuple[dict[str, Any], dict[str, Any]]:
    account = r.choice(customer["accounts"])
    card = r.choice(account["cards"])
    return account, card


def _base_event(customer: dict[str, Any], profile: dict[str, Any], merchants: list[dict[str, Any]], r: random.Random) -> dict[str, Any]:
    account, card = _pick_card(customer, r)
    category = r.choice(profile["typical_merchant_categories"])
    candidates = [m for m in merchants if m["category"] == category] or merchants
    merchant = r.choice(candidates)
    amount = max(1.0, round(r.gauss(profile["avg_transaction_amount"], profile["stddev_transaction_amount"]), 2))
    channel = r.choice(profile["typical_channels"])
    loc = customer["home_location"]

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "transaction",
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        "customer_id": customer["customer_id"],
        "account_id": account["account_id"],
        "card_id": card["card_id"],
        "amount": amount,
        "currency": "USD",
        "merchant_id": merchant["merchant_id"],
        "merchant_category": merchant["category"],
        "channel": channel,
        "device_id": None,
        "location": {
            "city": loc["city"],
            "country": loc["country"],
            "lat": loc["lat"],
            "lon": loc["lon"],
        },
    }


def make_normal_event(customer: dict[str, Any], profile: dict[str, Any], merchants: list[dict[str, Any]], r: random.Random) -> dict[str, Any]:
    return _base_event(customer, profile, merchants, r)


def make_amount_anomaly_event(customer: dict[str, Any], profile: dict[str, Any], merchants: list[dict[str, Any]], r: random.Random) -> dict[str, Any]:
    event = _base_event(customer, profile, merchants, r)
    multiplier = r.uniform(6, 15)
    event["amount"] = round(profile["avg_transaction_amount"] * multiplier, 2)
    # Anomalous purchases skew toward higher-risk, unfamiliar categories.
    unfamiliar = [m for m in merchants if m["category"] not in profile["typical_merchant_categories"]]
    if unfamiliar:
        merchant = r.choice(unfamiliar)
        event["merchant_id"] = merchant["merchant_id"]
        event["merchant_category"] = merchant["category"]
    return event


def make_velocity_burst(customer: dict[str, Any], profile: dict[str, Any], merchants: list[dict[str, Any]], r: random.Random) -> list[dict[str, Any]]:
    """A handful of small, rapid transactions on one card — card-testing pattern."""
    account, card = _pick_card(customer, r)
    burst_size = r.randint(4, 8)
    now = dt.datetime.utcnow()
    events = []
    for i in range(burst_size):
        merchant = r.choice(merchants)
        events.append(
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "transaction",
                "timestamp": (now + dt.timedelta(seconds=i * r.uniform(2, 8))).isoformat() + "Z",
                "customer_id": customer["customer_id"],
                "account_id": account["account_id"],
                "card_id": card["card_id"],
                "amount": round(r.uniform(1, 15), 2),
                "currency": "USD",
                "merchant_id": merchant["merchant_id"],
                "merchant_category": merchant["category"],
                "channel": "online",
                "device_id": None,
                "location": {
                    "city": customer["home_location"]["city"],
                    "country": customer["home_location"]["country"],
                    "lat": customer["home_location"]["lat"],
                    "lon": customer["home_location"]["lon"],
                },
            }
        )
    return events


def generate_events(count: int, anomaly_rate: float, burst_rate: float, seed: int):
    r = random.Random(seed)
    customers = load_fixture("customers.json")
    merchants = load_fixture("merchants.json")
    behavior_by_customer = {p["customer_id"]: p for p in load_fixture("customer_behavior.json")}

    produced = 0
    while produced < count:
        customer = r.choice(customers)
        profile = behavior_by_customer[customer["customer_id"]]

        roll = r.random()
        if roll < burst_rate:
            events = make_velocity_burst(customer, profile, merchants, r)
        elif roll < burst_rate + anomaly_rate:
            events = [make_amount_anomaly_event(customer, profile, merchants, r)]
        else:
            events = [make_normal_event(customer, profile, merchants, r)]

        for event in events:
            yield event
            produced += 1
            if produced >= count:
                return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sink", choices=["kafka", "stdout", "file"], default="stdout")
    parser.add_argument("--topic", default="transactions")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--rate", type=float, default=0, help="events/sec; 0 = as fast as possible")
    parser.add_argument("--anomaly-rate", type=float, default=0.05, help="fraction of amount-anomaly events")
    parser.add_argument("--burst-rate", type=float, default=0.03, help="fraction of high-velocity bursts")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    sink = Sink(args.sink, args.topic)
    seed = args.seed if args.seed is not None else random.randrange(1_000_000)

    for event in generate_events(args.count, args.anomaly_rate, args.burst_rate, seed):
        validate_event(event, TRANSACTION_SCHEMA)
        sink.send(event, key=event["customer_id"])
        if args.rate > 0:
            time.sleep(1.0 / args.rate)

    sink.flush()
    print(f"Sent {sink.sent_count} transaction events via sink={args.sink}")


if __name__ == "__main__":
    main()
