"""
Builders for `transactions` and `login-events` payloads.

Every event carries `timestamp` = the moment it is built (UTC, millisecond
precision). Flink uses that field as event time, so events must be produced
roughly in the order they are built -- see docs/decisions.md ("event time").
"""

from __future__ import annotations

import datetime as dt
import random
import time
from typing import Any, Optional

from .reference import FAR_FLUNG_CITIES, HIGH_RISK_CATEGORIES, new_uuid

AUTH_METHODS = ["password", "otp", "biometric"]
FAILURE_REASONS = ["bad_password", "otp_timeout", "otp_mismatch"]


class Clock:
    """Wall-clock time. `SimulatedClock` swaps in for tests so scenarios can
    be replayed instantly with realistic spacing between events."""

    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class SimulatedClock(Clock):
    def __init__(self, start: dt.datetime):
        self._t = start

    def now(self) -> dt.datetime:
        return self._t

    def sleep(self, seconds: float) -> None:
        self._t += dt.timedelta(seconds=seconds)


CLOCK: Clock = Clock()


def use_clock(clock: Clock) -> None:
    global CLOCK
    CLOCK = clock


def now_iso() -> str:
    return CLOCK.now().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _ip(r: random.Random) -> str:
    return f"{r.randint(1, 223)}.{r.randint(0, 255)}.{r.randint(0, 255)}.{r.randint(1, 254)}"


class World:
    """Indexes the reference data so builders can look things up quickly."""

    def __init__(self, ref: dict[str, Any]):
        self.customers = ref["customers"]
        self.by_id = {c["customer_id"]: c for c in self.customers}
        self.profiles = {p["customer_id"]: p for p in ref["customer_profiles"]}
        self.merchants = ref["merchants"]
        self.merchants_by_cat: dict[str, list] = {}
        for m in self.merchants:
            self.merchants_by_cat.setdefault(m["category"], []).append(m)
        self.devices_by_customer: dict[str, list] = {}
        for d in ref["devices"]:
            if d["customer_id"]:
                self.devices_by_customer.setdefault(d["customer_id"], []).append(d)
        self.untrusted_devices = [d for d in ref["devices"] if not d["trusted"]]

    def card(self, customer_id: str) -> tuple[dict, dict]:
        c = self.by_id[customer_id]
        account = c["accounts"][0]
        return account, account["cards"][0]

    def merchant(self, r: random.Random, category: Optional[str] = None,
                 risky: bool = False) -> dict:
        if category:
            return r.choice(self.merchants_by_cat[category])
        if risky:
            return r.choice([m for m in self.merchants if m["category"] in HIGH_RISK_CATEGORIES])
        return r.choice(self.merchants)


def transaction(world: World, r: random.Random, customer_id: str, *,
                amount: Optional[float] = None, merchant: Optional[dict] = None,
                channel: Optional[str] = None, location: Optional[dict] = None) -> dict[str, Any]:
    """A transaction; unspecified fields are drawn from the customer's normal behavior."""
    customer = world.by_id[customer_id]
    profile = world.profiles[customer_id]
    account, card = world.card(customer_id)
    if merchant is None:
        merchant = world.merchant(r, category=r.choice(profile["typical_merchant_categories"]))
    if amount is None:
        amount = max(1.0, round(r.gauss(profile["avg_transaction_amount"],
                                        profile["stddev_transaction_amount"]), 2))
    home = customer["home_location"]
    return {
        "event_id": new_uuid(r),
        "event_type": "transaction",
        "timestamp": now_iso(),
        "customer_id": customer_id,
        "account_id": account["account_id"],
        "card_id": card["card_id"],
        "amount": round(amount, 2),
        "currency": "USD",
        "merchant_id": merchant["merchant_id"],
        "merchant_category": merchant["category"],
        "channel": channel or r.choice(profile["typical_channels"]),
        "device_id": None,
        "location": location or {"city": home["city"], "country": home["country"],
                                 "lat": home["lat"], "lon": home["lon"]},
    }


def login(world: World, r: random.Random, customer_id: str, *,
          success: bool = True, device_id: Optional[str] = None,
          city: Optional[str] = None, country: Optional[str] = None,
          failure_reason: Optional[str] = None) -> dict[str, Any]:
    """A login; defaults to a successful login from a trusted device at home."""
    customer = world.by_id[customer_id]
    if device_id is None:
        device_id = r.choice(world.devices_by_customer[customer_id])["device_id"]
    home = customer["home_location"]
    return {
        "event_id": new_uuid(r),
        "event_type": "login",
        "timestamp": now_iso(),
        "customer_id": customer_id,
        "device_id": device_id,
        "ip_address": _ip(r),
        "location": {"city": city or home["city"], "country": country or home["country"]},
        "auth_method": r.choice(AUTH_METHODS),
        "success": success,
        "failure_reason": None if success else (failure_reason or r.choice(FAILURE_REASONS)),
    }


def far_city(r: random.Random) -> tuple[str, str]:
    city, country, _, _ = r.choice(FAR_FLUNG_CITIES)
    return city, country
