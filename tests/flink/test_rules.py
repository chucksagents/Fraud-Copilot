"""Runs every rule on a real (local, in-process) Flink and checks that each
story produces exactly the alerts the lab promises. Skipped when PyFlink
isn't installed -- see tests/flink/harness.py for setup."""

import collections
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("pyflink")

from harness import build_events, run_rules  # noqa: E402

from datagen.reference import PERSONA_IDS  # noqa: E402
from datagen.scenarios import SCENARIOS  # noqa: E402


@pytest.fixture(scope="module")
def alerts():
    with tempfile.TemporaryDirectory() as tmp:
        build_events(Path(tmp))
        yield run_rules(Path(tmp))


def test_each_story_fires_exactly_its_expected_rules(alerts):
    fired = collections.defaultdict(list)
    for a in alerts:
        if a["customer_id"] in PERSONA_IDS:
            fired[a["customer_id"]].append(a["rule_triggered"])
    for sc in SCENARIOS.values():
        assert sorted(fired[sc.customer_id]) == sorted(sc.expected_rules), sc.name


def test_severities(alerts):
    sev = {(a["customer_id"], a["rule_triggered"]): a["severity"] for a in alerts}
    assert sev[("cust_demo_omar", "high_velocity")] == "high"          # tiny amounts
    assert sev[("cust_demo_maya", "new_or_unusual_device")] == "medium" # foreign login
    assert sev[("cust_demo_maya", "amount_anomaly")] == "high"         # unfamiliar category
    assert sev[("cust_demo_raj", "amount_anomaly")] == "high"          # 13x, familiar category
    assert sev[("cust_demo_lena", "impossible_travel")] == "high"


def test_evidence_carries_what_the_investigation_needs(alerts):
    raj = next(a for a in alerts if a["customer_id"] == "cust_demo_raj")
    assert raj["evidence"]["familiar_category"] == "true"
    lena = next(a for a in alerts if a["customer_id"] == "cust_demo_lena")
    assert {lena["evidence"]["first_country"], lena["evidence"]["second_country"]} == {"JP", "GB"}


def test_alert_ids_are_unique_and_deterministic(alerts):
    ids = [a["alert_id"] for a in alerts]
    assert len(ids) == len(set(ids))
    with tempfile.TemporaryDirectory() as tmp:
        build_events(Path(tmp))
        again = {a["alert_id"] for a in run_rules(Path(tmp))}
    assert again == set(ids)  # replaying the same events yields the same alerts


def test_background_traffic_is_mostly_quiet(alerts):
    noise = [a for a in alerts if a["customer_id"] not in PERSONA_IDS]
    assert len(noise) <= 2, noise
