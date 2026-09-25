"""
Static reference data: customers, devices, merchants, behavior profiles, and
a history of previously resolved fraud cases.

Everything is derived from one seeded RNG, so the same seed always produces
the same IDs. The lab docs rely on that: they refer to the four "story"
customers (cust_demo_*) by ID, and those are identical on every machine.

Nothing here is real customer data.
"""

from __future__ import annotations

import datetime as dt
import random
import uuid
from typing import Any

DEFAULT_SEED = 1337

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Amara",
    "Priya", "Wei", "Fatima", "Diego", "Sofia", "Kwame", "Aisha", "Liam",
    "Noor",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Chen", "Kumar", "Nguyen", "Okafor", "Haddad", "Kowalski", "Andersson",
]

# (city, country, lat, lon)
CITIES = [
    ("New York", "US", 40.7128, -74.0060),
    ("Chicago", "US", 41.8781, -87.6298),
    ("Austin", "US", 30.2672, -97.7431),
    ("Toronto", "CA", 43.6532, -79.3832),
    ("London", "GB", 51.5074, -0.1278),
    ("Dublin", "IE", 53.3498, -6.2603),
    ("Berlin", "DE", 52.5200, 13.4050),
    ("Singapore", "SG", 1.3521, 103.8198),
    ("Sydney", "AU", -33.8688, 151.2093),
]

# Used only to inject suspicious activity: far from every home city above.
FAR_FLUNG_CITIES = [
    ("Reykjavik", "IS", 64.1466, -21.9426),
    ("Ulaanbaatar", "MN", 47.8864, 106.9057),
    ("Nairobi", "KE", -1.2921, 36.8219),
    ("Manila", "PH", 14.5995, 120.9842),
]

MERCHANT_CATEGORIES = [
    "grocery", "restaurant", "gas_station", "electronics", "travel",
    "online_retail", "utilities", "entertainment", "pharmacy",
    "home_improvement", "clothing", "subscription", "gift_cards",
]

CATEGORY_SUFFIX = {
    "grocery": "Market", "restaurant": "Kitchen", "gas_station": "Fuel",
    "electronics": "Electronics", "travel": "Travel", "online_retail": "Online",
    "utilities": "Utilities", "entertainment": "Entertainment",
    "pharmacy": "Pharmacy", "home_improvement": "Home & Hardware",
    "clothing": "Apparel", "subscription": "Digital Services",
    "gift_cards": "Gift Cards",
}

# Categories fraudsters favor (easy to resell or low-friction online).
HIGH_RISK_CATEGORIES = {"online_retail", "subscription", "gift_cards", "entertainment"}

MERCHANT_NAME_STEMS = [
    "Northgate", "Riverside", "Summit", "Cedar", "Harbor", "Union",
    "Pioneer", "Lakeside", "Maple", "Granite", "Meridian", "Coastal",
    "Foothill", "Wellspring", "Ironwood", "Brightline",
]

DEVICE_OS = {
    "mobile": ["iOS 18", "Android 15"],
    "desktop": ["Windows 11", "macOS 15"],
    "tablet": ["iPadOS 18", "Android 15"],
}

RISK_TIERS = ["low", "low", "low", "medium", "medium", "high"]

# A fixed "today" keeps generated dates identical across machines and runs.
REFERENCE_DATE = dt.date(2026, 9, 1)


def new_id(prefix: str, r: random.Random) -> str:
    """Deterministic, realistic-looking id drawn from the seeded RNG."""
    return f"{prefix}_{r.getrandbits(48):012x}"


def new_uuid(r: random.Random) -> str:
    return str(uuid.UUID(int=r.getrandbits(128), version=4))


def _days_ago(r: random.Random, lo: int, hi: int) -> str:
    return (REFERENCE_DATE - dt.timedelta(days=r.randint(lo, hi))).isoformat()


# ---------------------------------------------------------------------------
# Story customers. The lab's scenarios target these four people, so their
# attributes are chosen by hand to make the investigation outcome depend on
# context the detection rules can't see (travel notices, familiar merchant
# categories, prior cases).
# ---------------------------------------------------------------------------

PERSONAS: list[dict[str, Any]] = [
    {
        "customer_id": "cust_demo_maya",
        "name": "Maya Chen",
        "home": ("New York", "US", 40.7128, -74.0060),
        "risk_tier": "low",
        "avg_amount": 64.0,
        "categories": ["grocery", "restaurant", "pharmacy", "clothing"],
        "channels": ["card_present", "online"],
        "devices": [("mobile", "iOS 18"), ("desktop", "macOS 15")],
        "travel_notices": [],
        "history": [],
        "story": "account_takeover",
    },
    {
        "customer_id": "cust_demo_omar",
        "name": "Omar Haddad",
        "home": ("Chicago", "US", 41.8781, -87.6298),
        "risk_tier": "medium",
        "avg_amount": 48.0,
        "categories": ["grocery", "gas_station", "restaurant"],
        "channels": ["card_present"],
        "devices": [("mobile", "Android 15")],
        "travel_notices": [],
        "history": [],
        "story": "card_testing",
    },
    {
        "customer_id": "cust_demo_lena",
        "name": "Lena Andersson",
        "home": ("London", "GB", 51.5074, -0.1278),
        "risk_tier": "low",
        "avg_amount": 85.0,
        "categories": ["travel", "restaurant", "online_retail", "entertainment"],
        "channels": ["card_present", "online"],
        "devices": [("mobile", "iOS 18"), ("desktop", "Windows 11")],
        # Lena is in Tokyo on business; her corporate laptop tunnels through
        # the London office VPN. Two logins from two countries minutes apart
        # is exactly what impossible_travel looks for, and it's legitimate.
        # Offsets are relative to "today" so the notice is always active.
        "travel_notices": [
            {"country": "JP", "start_offset_days": -5, "end_offset_days": 9,
             "note": "Business trip to Tokyo; uses corporate VPN (exits in London)."}
        ],
        "history": [
            {"rule": "impossible_travel", "action": "contact_customer",
             "outcome": "false_positive", "days_ago": 210,
             "summary": "Logins from GB and SG 9 minutes apart; customer confirmed corporate VPN during a Singapore trip."},
        ],
        "story": "travel_vpn",
    },
    {
        "customer_id": "cust_demo_raj",
        "name": "Raj Kumar",
        "home": ("Austin", "US", 30.2672, -97.7431),
        "risk_tier": "low",
        "avg_amount": 120.0,
        "categories": ["electronics", "home_improvement", "grocery", "restaurant"],
        "channels": ["card_present", "online"],
        "devices": [("desktop", "Windows 11"), ("mobile", "Android 15")],
        "travel_notices": [],
        "history": [
            {"rule": "amount_anomaly", "action": "contact_customer",
             "outcome": "false_positive", "days_ago": 300,
             "summary": "$1,900 at an electronics retailer (13x average); customer confirmed a TV purchase."},
        ],
        "story": "big_purchase",
    },
]

PERSONA_IDS = {p["customer_id"] for p in PERSONAS}


def _card(account_type: str, r: random.Random) -> dict[str, Any]:
    return {
        "card_id": new_id("card", r),
        "card_type": "debit" if account_type == "checking" else "credit",
        "last4": f"{r.randint(0, 9999):04d}",
        "issued_at": _days_ago(r, 30, 1800),
    }


def _account(r: random.Random, n_cards: int | None = None) -> dict[str, Any]:
    account_type = r.choice(["checking", "credit"])
    return {
        "account_id": new_id("acct", r),
        "account_type": account_type,
        "opened_at": _days_ago(r, 90, 3650),
        "cards": [_card(account_type, r) for _ in range(n_cards or r.choice([1, 1, 2]))],
    }


def _device(customer_id: str | None, r: random.Random, trusted: bool,
            device_type: str | None = None, os_name: str | None = None) -> dict[str, Any]:
    device_type = device_type or r.choice(list(DEVICE_OS))
    return {
        "device_id": new_id("dev", r),
        "customer_id": customer_id,
        "device_type": device_type,
        "os": os_name or r.choice(DEVICE_OS[device_type]),
        "first_seen": _days_ago(r, 30, 900),
        "trusted": trusted,
    }


def _location(city: tuple) -> dict[str, Any]:
    name, country, lat, lon = city
    return {"city": name, "country": country, "lat": lat, "lon": lon}


def generate(seed: int = DEFAULT_SEED, n_customers: int = 200, n_merchants: int = 60,
             n_history: int = 40, today: dt.date | None = None) -> dict[str, Any]:
    """Build the full reference dataset. Returns a dict of named tables.

    Deterministic for a given seed. `today` only affects travel-notice
    dates (kept relative so the story stays true whenever the lab is run).
    """
    r = random.Random(seed)
    today = today or dt.datetime.now(dt.timezone.utc).date()
    customers: list[dict[str, Any]] = []
    devices: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    # --- merchants ---------------------------------------------------------
    merchants = []
    for cat in MERCHANT_CATEGORIES:  # guarantee every category has merchants
        for _ in range(max(2, n_merchants // len(MERCHANT_CATEGORIES))):
            city = r.choice(CITIES)
            merchants.append({
                "merchant_id": new_id("merch", r),
                "name": f"{r.choice(MERCHANT_NAME_STEMS)} {CATEGORY_SUFFIX[cat]}",
                "category": cat,
                "risk_level": (r.choice(["medium", "high", "high"]) if cat in HIGH_RISK_CATEGORIES
                               else r.choice(["low", "low", "low", "medium"])),
                "country": city[1],
            })

    # --- story customers ---------------------------------------------------
    for p in PERSONAS:
        cid = p["customer_id"]
        customers.append({
            "customer_id": cid,
            "name": p["name"],
            "email": p["name"].lower().replace(" ", ".") + "@example.com",
            "phone": f"+1{r.randint(2000000000, 9999999999)}",
            "risk_tier": p["risk_tier"],
            "customer_since": _days_ago(r, 1500, 3000),
            "home_location": _location(p["home"]),
            "accounts": [_account(r, n_cards=1)],
            "travel_notices": [
                {"country": n["country"], "note": n["note"],
                 "start": (today + dt.timedelta(days=n["start_offset_days"])).isoformat(),
                 "end": (today + dt.timedelta(days=n["end_offset_days"])).isoformat()}
                for n in p["travel_notices"]
            ],
        })
        own = [_device(cid, r, True, t, o) for t, o in p["devices"]]
        devices += own
        profiles.append(_profile(customers[-1], own, r, avg=p["avg_amount"],
                                 categories=p["categories"], channels=p["channels"]))
        for h in p["history"]:
            history.append(_history_case(cid, r, h))

    # --- everyone else -----------------------------------------------------
    for _ in range(n_customers - len(PERSONAS)):
        first, last = r.choice(FIRST_NAMES), r.choice(LAST_NAMES)
        cid = new_id("cust", r)
        customers.append({
            "customer_id": cid,
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}{r.randint(1, 999)}@example.com",
            "phone": f"+1{r.randint(2000000000, 9999999999)}",
            "risk_tier": r.choice(RISK_TIERS),
            "customer_since": _days_ago(r, 90, 3650),
            "home_location": _location(r.choice(CITIES)),
            "accounts": [_account(r) for _ in range(r.choice([1, 1, 2]))],
            "travel_notices": [],
        })
        own = [_device(cid, r, True) for _ in range(r.choice([1, 1, 2, 3]))]
        devices += own
        profiles.append(_profile(customers[-1], own, r))

    # Untrusted "attacker" devices never linked to any customer's history.
    for _ in range(max(20, n_customers // 5)):
        devices.append(_device(None, r, trusted=False))

    # Background history of resolved cases for non-story customers.
    others = [c for c in customers if c["customer_id"] not in PERSONA_IDS]
    for c in r.sample(others, k=min(n_history, len(others))):
        history.append(_history_case(c["customer_id"], r))

    return {
        "customers": customers,
        "devices": devices,
        "merchants": merchants,
        "customer_profiles": profiles,
        "case_history": history,
    }


def _profile(customer: dict[str, Any], own_devices: list[dict[str, Any]], r: random.Random,
             avg: float | None = None, categories: list[str] | None = None,
             channels: list[str] | None = None) -> dict[str, Any]:
    """The per-customer baseline. Flink joins against this (via the
    customer-profiles topic) and the API serves it to the agents."""
    avg = avg if avg is not None else round(r.uniform(20, 250), 2)
    home = customer["home_location"]
    return {
        "customer_id": customer["customer_id"],
        "home_city": home["city"],
        "home_country": home["country"],
        "avg_transaction_amount": avg,
        "stddev_transaction_amount": round(avg * r.uniform(0.2, 0.4), 2),
        "typical_merchant_categories": categories or r.sample(
            [c for c in MERCHANT_CATEGORIES if c != "gift_cards"], k=r.randint(3, 5)),
        "typical_channels": channels or r.choice([["card_present", "online"], ["card_present"], ["online"]]),
        "typical_countries": [home["country"]],
        "trusted_device_ids": [d["device_id"] for d in own_devices],
        "avg_daily_transaction_count": round(r.uniform(0.5, 4.0), 1),
    }


_HISTORY_TEMPLATES = {
    "high_velocity": "{n} transactions in {mins} minutes at unrelated online merchants.",
    "multiple_failed_logins": "{n} failed logins, then a success from a new device.",
    "new_or_unusual_device": "Login from a device never seen on this account.",
    "impossible_travel": "Logins from two countries {mins} minutes apart.",
    "amount_anomaly": "Transaction {mult}x the customer's average spend.",
}
_HISTORY_OUTCOMES = [
    ("card_lock", "confirmed_fraud"),
    ("contact_customer", "false_positive"),
    ("no_action", "false_positive"),
    ("escalate", "confirmed_fraud"),
]


def _history_case(customer_id: str, r: random.Random, spec: dict | None = None) -> dict[str, Any]:
    if spec:
        rule, action, outcome = spec["rule"], spec["action"], spec["outcome"]
        days_ago, summary = spec["days_ago"], spec["summary"]
    else:
        rule = r.choice(list(_HISTORY_TEMPLATES))
        action, outcome = r.choice(_HISTORY_OUTCOMES)
        days_ago = r.randint(5, 400)
        summary = _HISTORY_TEMPLATES[rule].format(
            n=r.randint(3, 9), mins=r.randint(2, 45), mult=round(r.uniform(3, 12), 1))
    resolved = dt.datetime.combine(REFERENCE_DATE, dt.time(12)) - dt.timedelta(days=days_ago)
    return {
        "case_id": new_id("hist", r),
        "customer_id": customer_id,
        "rule_triggered": rule,
        "action_taken": action,
        "outcome": outcome,
        "resolved_at": resolved.isoformat() + "Z",
        "summary": summary,
    }
