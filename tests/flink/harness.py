"""
Run the real rule SQL (flink/rules/*.sql) on a local Flink, against events
produced by the real scenario code, and return the alerts.

The table DDL is read from flink/local/tables.sql and only the connector
options are swapped (Kafka -> JSON-lines files), so the columns, types and
watermarks under test are exactly the ones the lab runs.

Needs PyFlink 1.20 (Python 3.8-3.11) and Java 11+:
    pip install "apache-flink==1.20.3"
Used by tests/flink/test_rules.py and by maintainers to regenerate
data/demo-seed.json:
    python tests/flink/harness.py --write-seed
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from datagen import events, reference  # noqa: E402
from datagen.__main__ import run_scenario  # noqa: E402
from datagen.scenarios import SCENARIOS, background  # noqa: E402
from datagen.sinks import Sink  # noqa: E402

TABLES_SQL = REPO / "flink" / "local" / "tables.sql"
RULES_DIR = REPO / "flink" / "rules"
SOURCE_FILES = {"transactions": "transactions.jsonl", "login_events": "login-events.jsonl",
                "customer_profiles": "customer_profiles.jsonl"}
START = dt.datetime(2026, 9, 25, 14, 0, tzinfo=dt.timezone.utc)


def build_events(workdir: Path, scenario_names=None, gap_seconds: float = 40,
                 noise_rate: float = 0.0) -> list[tuple[str, dict]]:
    """Background traffic with each scenario played in turn, on a simulated
    clock. Writes the JSON-lines inputs Flink will read; returns the events."""
    events.use_clock(events.SimulatedClock(START))
    ref = reference.generate(reference.DEFAULT_SEED)
    world = events.World(ref)
    sink = Sink("memory")
    bg = background(world, random.Random(7), anomaly_rate=noise_rate)

    def gap():
        end = events.CLOCK.now() + dt.timedelta(seconds=gap_seconds)
        while events.CLOCK.now() < end:
            topic, e = next(bg)
            sink.send(topic, e)
            events.CLOCK.sleep(1.0)  # same rate as `datagen simulate`'s default

    gap()
    for name in scenario_names or list(SCENARIOS):
        run_scenario(name, sink, reference.DEFAULT_SEED, verbose=False)
        gap()
    events.use_clock(events.Clock())

    by_topic: dict[str, list] = {"transactions": [], "login-events": []}
    for topic, e in sink.records:
        by_topic[topic].append(e)
    for topic, rows in by_topic.items():
        rows.sort(key=lambda e: e["timestamp"])
        (workdir / f"{topic}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in rows))
    (workdir / "customer_profiles.jsonl").write_text(
        "".join(json.dumps(p) + "\n" for p in ref["customer_profiles"]))
    return sink.records


def _statements(sql: str) -> list[str]:
    no_comments = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def run_rules(workdir: Path, rule_files=None) -> list[dict]:
    from pyflink.table import EnvironmentSettings, TableEnvironment

    t = TableEnvironment.create(EnvironmentSettings.in_streaming_mode())
    for stmt in _statements(TABLES_SQL.read_text()):
        if stmt.upper().startswith("SET"):
            k, v = re.findall(r"'([^']*)'", stmt)
            t.get_config().set(k, v)
            continue
        name = re.search(r"CREATE TABLE IF NOT EXISTS (\w+)", stmt).group(1)
        if name not in SOURCE_FILES:
            continue  # the sink; we collect query results directly instead
        path = workdir / SOURCE_FILES[name]
        stmt = re.sub(r"WITH \(.*\)\s*$",
                      f"WITH ('connector'='filesystem','path'='{path}','format'='json',"
                      "'json.timestamp-format.standard'='ISO-8601')", stmt, flags=re.S)
        t.execute_sql(stmt)

    alerts = []
    for rule in rule_files or sorted(RULES_DIR.glob("*.sql")):
        sql = _statements(Path(rule).read_text())[0]
        select = re.sub(r"^INSERT INTO fraud_alerts\s*", "", sql, flags=re.I)
        with t.sql_query(select).execute().collect() as rows:
            for row in rows:
                (alert_id, generated_at, customer_id, account_id, rule_name, severity,
                 related, evidence, status) = row
                alerts.append({"alert_id": alert_id, "generated_at": generated_at,
                               "customer_id": customer_id, "account_id": account_id,
                               "rule_triggered": rule_name, "severity": severity,
                               "related_event_ids": list(related), "evidence": dict(evidence),
                               "status": status})
    return alerts


def write_demo_seed(out: Path) -> None:
    """Capture the four stories -- their events and the alerts real Flink
    produced -- so `python -m datagen seed-demo` can load them without
    Kafka or Flink running. Timestamps are rebased to 'now' on load."""
    with tempfile.TemporaryDirectory() as tmp:
        records = build_events(Path(tmp))
        alerts = run_rules(Path(tmp))
    personas = reference.PERSONA_IDS
    story_events = [dict(e, topic=topic) for topic, e in records if e["customer_id"] in personas]
    story_alerts = [a for a in alerts if a["customer_id"] in personas]
    story_alerts.sort(key=lambda a: a["generated_at"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "about": "Events and Flink-generated alerts for the four story scenarios. "
                 "Regenerate with: python tests/flink/harness.py --write-seed",
        "captured_at": START.isoformat().replace("+00:00", "Z"),
        "events": story_events,
        "alerts": story_alerts,
    }, indent=1) + "\n")
    print(f"wrote {len(story_alerts)} alerts, {len(story_events)} events to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-seed", action="store_true")
    args = ap.parse_args()
    if args.write_seed:
        write_demo_seed(REPO / "data" / "demo-seed.json")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            build_events(Path(tmp))
            for a in run_rules(Path(tmp)):
                print(f"{a['generated_at']}  {a['customer_id']:<18} {a['rule_triggered']:<24} "
                      f"{a['severity']:<7} {a['evidence']}")
