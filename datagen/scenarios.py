"""
Scripted fraud (and not-fraud) stories, plus background traffic.

Each scenario targets one of the story customers in reference.PERSONAS and
is written so the *detection* outcome is fixed (which rules fire) while the
*right response* depends on context only an investigation can find. That
contrast is the point of the lab:

  scenario          customer         rules expected to fire               right call
  ----------------  ---------------  -----------------------------------  -----------------
  account_takeover  cust_demo_maya   failed logins, new device,           lock card, link
                                     impossible travel, amount anomaly    the related cases
  card_testing      cust_demo_omar   high velocity                        lock card
  travel_vpn        cust_demo_lena   impossible travel                    contact customer
                                                                          (travel notice + VPN)
  big_purchase      cust_demo_raj    amount anomaly                       contact customer
                                                                          (familiar category)

A scenario is a list of Steps: wait `delay` seconds, then emit one event.
Delays are real seconds when run live, simulated seconds in tests.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from . import events as ev
from .events import World
from .reference import PERSONA_IDS

TX, LOGIN = "transactions", "login-events"


@dataclass
class Step:
    delay: float
    topic: str
    build: Callable[[], dict[str, Any]]


@dataclass
class Scenario:
    name: str
    customer_id: str
    summary: str
    expected_rules: list[str]
    expected_action: str
    steps: Callable[[World, random.Random], list[Step]]


def _account_takeover(w: World, r: random.Random) -> list[Step]:
    cid = "cust_demo_maya"
    attacker = r.choice(w.untrusted_devices)["device_id"]
    city, country = "Reykjavik", "IS"
    gift_cards = w.merchant(r, category="gift_cards")
    steps = [
        # Maya checks her banking app at home in New York.
        Step(0, LOGIN, lambda: ev.login(w, r, cid)),
        # Minutes later (seconds, in lab time) someone else tries her password.
        *[Step(2.5, LOGIN, lambda: ev.login(w, r, cid, success=False, device_id=attacker,
                                            city=city, country=country,
                                            failure_reason="bad_password"))
          for _ in range(4)],
        Step(3, LOGIN, lambda: ev.login(w, r, cid, device_id=attacker, city=city, country=country)),
        # ...and immediately spends her money on something easy to resell.
        Step(6, TX, lambda: ev.transaction(w, r, cid, amount=1450.00, merchant=gift_cards,
                                           channel="online",
                                           location={"city": city, "country": country,
                                                     "lat": 64.1466, "lon": -21.9426})),
    ]
    return steps


def _card_testing(w: World, r: random.Random) -> list[Step]:
    cid = "cust_demo_omar"
    steps = []
    for i in range(7):
        m = w.merchant(r, risky=True)
        amt = round(r.uniform(1, 9), 2)
        steps.append(Step(0 if i == 0 else r.uniform(2, 4), TX,
                          lambda m=m, amt=amt: ev.transaction(w, r, cid, amount=amt, merchant=m,
                                                              channel="online")))
    return steps


def _travel_vpn(w: World, r: random.Random) -> list[Step]:
    cid = "cust_demo_lena"
    mobile, laptop = [d["device_id"] for d in w.devices_by_customer[cid]]
    restaurant = w.merchant(r, category="restaurant")
    return [
        # Lena, in Tokyo, logs in from her phone...
        Step(0, LOGIN, lambda: ev.login(w, r, cid, device_id=mobile, city="Tokyo", country="JP")),
        # ...pays for dinner...
        Step(4, TX, lambda: ev.transaction(w, r, cid, amount=92.40, merchant=restaurant,
                                           channel="card_present",
                                           location={"city": "Tokyo", "country": "JP",
                                                     "lat": 35.6762, "lon": 139.6503})),
        # ...then opens her work laptop, whose VPN exits in London.
        Step(20, LOGIN, lambda: ev.login(w, r, cid, device_id=laptop, city="London", country="GB")),
    ]


def _big_purchase(w: World, r: random.Random) -> list[Step]:
    cid = "cust_demo_raj"
    desktop = w.devices_by_customer[cid][0]["device_id"]
    electronics = w.merchant(r, category="electronics")
    return [
        Step(0, LOGIN, lambda: ev.login(w, r, cid, device_id=desktop)),
        Step(8, TX, lambda: ev.transaction(w, r, cid, amount=1560.00, merchant=electronics,
                                           channel="card_present")),
    ]


SCENARIOS: dict[str, Scenario] = {
    s.name: s for s in [
        Scenario("account_takeover", "cust_demo_maya",
                 "Password guessing from Reykjavik, a successful login from an unknown "
                 "device, then a $1,450 gift-card purchase.",
                 ["multiple_failed_logins", "new_or_unusual_device", "impossible_travel",
                  "amount_anomaly"], "card_lock", _account_takeover),
        Scenario("card_testing", "cust_demo_omar",
                 "Seven tiny online purchases at unrelated merchants within ~25 seconds.",
                 ["high_velocity"], "card_lock", _card_testing),
        Scenario("travel_vpn", "cust_demo_lena",
                 "Logins from Tokyo and London 24 seconds apart, from two trusted devices, "
                 "while a travel notice for Japan is on file.",
                 ["impossible_travel"], "contact_customer", _travel_vpn),
        Scenario("big_purchase", "cust_demo_raj",
                 "A $1,560 in-store electronics purchase, 13x Raj's average, in his home city.",
                 ["amount_anomaly"], "contact_customer", _big_purchase),
    ]
}


def background(w: World, r: random.Random, anomaly_rate: float = 0.02) -> Iterator[tuple[str, dict]]:
    """Endless normal traffic for non-story customers, with occasional
    low-stakes anomalies so the case queue has realistic noise in it."""
    pool = [c["customer_id"] for c in w.customers if c["customer_id"] not in PERSONA_IDS]
    while True:
        cid = r.choice(pool)
        roll = r.random()
        if roll < anomaly_rate:
            kind = r.choice(["amount", "device", "velocity", "failed"])
            if kind == "amount":
                avg = w.profiles[cid]["avg_transaction_amount"]
                yield TX, ev.transaction(w, r, cid, amount=round(avg * r.uniform(6, 9), 2))
            elif kind == "device":
                yield LOGIN, ev.login(w, r, cid, device_id=r.choice(w.untrusted_devices)["device_id"])
            elif kind == "velocity":
                for _ in range(r.randint(4, 5)):
                    yield TX, ev.transaction(w, r, cid)
            else:
                for _ in range(3):
                    yield LOGIN, ev.login(w, r, cid, success=False)
        elif roll < 0.6:
            yield TX, ev.transaction(w, r, cid)
        else:
            yield LOGIN, ev.login(w, r, cid)
