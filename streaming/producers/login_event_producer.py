"""
Emit synthetic `login-events`, validated against
docs/schemas/login-event.schema.json.

Most events are a single successful login from one of the customer's
trusted devices. A configurable fraction are deliberately anomalous:
  - a burst of failed logins before/without a success
  - a login from an untrusted/new device
  - "impossible travel": two logins for the same customer, minutes apart,
    from locations that are not physically reachable in that time

Usage:
  python3 login_event_producer.py --sink stdout --count 50
  python3 login_event_producer.py --sink file --count 500

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
    from .common import FIXTURES_DIR, Sink, load_fixture, load_schema, validate_event
except ImportError:
    from common import FIXTURES_DIR, Sink, load_fixture, load_schema, validate_event

LOGIN_SCHEMA = load_schema("login-event.schema.json")

AUTH_METHODS = ["password", "otp", "biometric"]
FAILURE_REASONS = ["bad_password", "otp_timeout", "otp_mismatch", "account_locked"]

FAR_FLUNG_CITIES = [
    ("Reykjavik", "IS"),
    ("Ulaanbaatar", "MN"),
    ("Nairobi", "KE"),
    ("Manila", "PH"),
]


def _devices_by_customer(devices: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_customer: dict[str, list[dict[str, Any]]] = {}
    for d in devices:
        if d["customer_id"]:
            by_customer.setdefault(str(d["customer_id"]), []).append(d)
    return by_customer


def make_normal_login(customer: dict[str, Any], own_devices: list[dict[str, Any]], r: random.Random) -> dict[str, Any]:
    device = r.choice(own_devices) if own_devices else None
    loc = customer["home_location"]
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "login",
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        "customer_id": customer["customer_id"],
        "device_id": device["device_id"] if device else str(uuid.uuid4()),
        "ip_address": f"{r.randint(1,223)}.{r.randint(0,255)}.{r.randint(0,255)}.{r.randint(1,254)}",
        "location": {"city": loc["city"], "country": loc["country"]},
        "auth_method": r.choice(AUTH_METHODS),
        "success": True,
        "failure_reason": None,
    }


def make_failed_login_burst(customer: dict[str, Any], own_devices: list[dict[str, Any]], r: random.Random) -> list[dict[str, Any]]:
    device = r.choice(own_devices) if own_devices else None
    loc = customer["home_location"]
    now = dt.datetime.utcnow()
    burst_size = r.randint(3, 6)
    events = []
    for i in range(burst_size):
        events.append(
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "login",
                "timestamp": (now + dt.timedelta(seconds=i * r.uniform(3, 10))).isoformat() + "Z",
                "customer_id": customer["customer_id"],
                "device_id": device["device_id"] if device else str(uuid.uuid4()),
                "ip_address": f"{r.randint(1,223)}.{r.randint(0,255)}.{r.randint(0,255)}.{r.randint(1,254)}",
                "location": {"city": loc["city"], "country": loc["country"]},
                "auth_method": r.choice(AUTH_METHODS),
                "success": False,
                "failure_reason": r.choice(FAILURE_REASONS),
            }
        )
    # Roughly half the time, cap the burst with an eventual success from a new device.
    if r.random() < 0.5:
        events.append(
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "login",
                "timestamp": (now + dt.timedelta(seconds=burst_size * 10 + 5)).isoformat() + "Z",
                "customer_id": customer["customer_id"],
                "device_id": str(uuid.uuid4()),
                "ip_address": f"{r.randint(1,223)}.{r.randint(0,255)}.{r.randint(0,255)}.{r.randint(1,254)}",
                "location": {"city": loc["city"], "country": loc["country"]},
                "auth_method": r.choice(AUTH_METHODS),
                "success": True,
                "failure_reason": None,
            }
        )
    return events


def make_new_device_login(customer: dict[str, Any], untrusted_devices: list[dict[str, Any]], r: random.Random) -> dict[str, Any]:
    device = r.choice(untrusted_devices)
    loc = customer["home_location"]
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "login",
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        "customer_id": customer["customer_id"],
        "device_id": device["device_id"],
        "ip_address": f"{r.randint(1,223)}.{r.randint(0,255)}.{r.randint(0,255)}.{r.randint(1,254)}",
        "location": {"city": loc["city"], "country": loc["country"]},
        "auth_method": r.choice(AUTH_METHODS),
        "success": True,
        "failure_reason": None,
    }


def make_impossible_travel_pair(customer: dict[str, Any], own_devices: list[dict[str, Any]], r: random.Random) -> list[dict[str, Any]]:
    device = r.choice(own_devices) if own_devices else None
    home_loc = customer["home_location"]
    far_city, far_country = r.choice(FAR_FLUNG_CITIES)
    now = dt.datetime.utcnow()
    minutes_apart = r.randint(2, 20)
    return [
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "login",
            "timestamp": now.isoformat() + "Z",
            "customer_id": customer["customer_id"],
            "device_id": device["device_id"] if device else str(uuid.uuid4()),
            "ip_address": f"{r.randint(1,223)}.{r.randint(0,255)}.{r.randint(0,255)}.{r.randint(1,254)}",
            "location": {"city": home_loc["city"], "country": home_loc["country"]},
            "auth_method": r.choice(AUTH_METHODS),
            "success": True,
            "failure_reason": None,
        },
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "login",
            "timestamp": (now + dt.timedelta(minutes=minutes_apart)).isoformat() + "Z",
            "customer_id": customer["customer_id"],
            "device_id": str(uuid.uuid4()),
            "ip_address": f"{r.randint(1,223)}.{r.randint(0,255)}.{r.randint(0,255)}.{r.randint(1,254)}",
            "location": {"city": far_city, "country": far_country},
            "auth_method": r.choice(AUTH_METHODS),
            "success": True,
            "failure_reason": None,
        },
    ]


def generate_events(count: int, failed_burst_rate: float, new_device_rate: float, travel_rate: float, seed: int):
    r = random.Random(seed)
    customers = load_fixture("customers.json")
    devices = load_fixture("devices.json")
    by_customer = _devices_by_customer(devices)
    untrusted_devices = [d for d in devices if not d["trusted"]]

    produced = 0
    while produced < count:
        customer = r.choice(customers)
        own_devices = by_customer.get(customer["customer_id"], [])

        roll = r.random()
        if roll < failed_burst_rate:
            events = make_failed_login_burst(customer, own_devices, r)
        elif roll < failed_burst_rate + new_device_rate:
            events = [make_new_device_login(customer, untrusted_devices, r)]
        elif roll < failed_burst_rate + new_device_rate + travel_rate:
            events = make_impossible_travel_pair(customer, own_devices, r)
        else:
            events = [make_normal_login(customer, own_devices, r)]

        for event in events:
            yield event
            produced += 1
            if produced >= count:
                return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sink", choices=["kafka", "stdout", "file"], default="stdout")
    parser.add_argument("--topic", default="login-events")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--rate", type=float, default=0, help="events/sec; 0 = as fast as possible")
    parser.add_argument("--failed-burst-rate", type=float, default=0.05)
    parser.add_argument("--new-device-rate", type=float, default=0.05)
    parser.add_argument("--travel-rate", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    sink = Sink(args.sink, args.topic)
    seed = args.seed if args.seed is not None else random.randrange(1_000_000)

    for event in generate_events(
        args.count, args.failed_burst_rate, args.new_device_rate, args.travel_rate, seed
    ):
        validate_event(event, LOGIN_SCHEMA)
        sink.send(event, key=event["customer_id"])
        if args.rate > 0:
            time.sleep(1.0 / args.rate)

    sink.flush()
    print(f"Sent {sink.sent_count} login events via sink={args.sink}")


if __name__ == "__main__":
    main()
