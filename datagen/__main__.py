"""
datagen -- synthetic data for the lab.

  python -m datagen personas                 the four story customers
  python -m datagen reference [--out DIR]    write reference data as JSON files
  python -m datagen load-reference           publish customer profiles to Kafka
  python -m datagen simulate [--rate 2]      background traffic until Ctrl-C
  python -m datagen scenario NAME            play one story (see --list)
  python -m datagen seed-demo                load pre-computed alerts into the
                                             fraud API (skip Kafka + Flink)

Every command accepts --sink stdout to print instead of sending to Kafka.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

from . import events, reference
from .events import World
from .scenarios import SCENARIOS, background
from .sinks import REPO_ROOT, TOPICS, Sink

DEMO_SEED_FILE = REPO_ROOT / "data" / "demo-seed.json"


def _world(seed: int) -> World:
    return World(reference.generate(seed))


def cmd_personas(args) -> None:
    ref = reference.generate(args.seed)
    by_id = {c["customer_id"]: c for c in ref["customers"]}
    print(f"{'customer_id':<18} {'name':<16} {'home':<18} scenario")
    for p in reference.PERSONAS:
        c = by_id[p["customer_id"]]
        home = f"{c['home_location']['city']}, {c['home_location']['country']}"
        print(f"{p['customer_id']:<18} {p['name']:<16} {home:<18} {p['story']}")


def cmd_reference(args) -> None:
    ref = reference.generate(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in ref.items():
        (out / f"{name}.json").write_text(json.dumps(rows, indent=2) + "\n")
        with open(out / f"{name}.jsonl", "w") as f:  # JSON-lines, for Flink's filesystem connector
            for row in rows:
                f.write(json.dumps(row) + "\n")
        print(f"  {name:<18} {len(rows):>4} rows")
    print(f"Wrote reference data to {out}/")


def cmd_load_reference(args) -> None:
    ref = reference.generate(args.seed)
    sink = Sink(args.sink)
    for p in ref["customer_profiles"]:
        sink.send("customer-profiles", p, key=p["customer_id"])
    sink.flush()
    print(f"Published {sink.count} customer profiles to '{TOPICS['customer-profiles']}'.")


def cmd_simulate(args) -> None:
    world, r = _world(args.seed), random.Random()
    sink = Sink(args.sink)
    deadline = time.time() + args.duration if args.duration else None
    interval = 1.0 / args.rate
    print(f"Background traffic at ~{args.rate} events/s (anomaly rate {args.anomaly_rate}). "
          "Ctrl-C to stop.", file=sys.stderr)
    try:
        for topic, event in background(world, r, args.anomaly_rate):
            sink.send(topic, event, key=event["customer_id"])
            if sink.count % 200 == 0:
                sink.flush()
                print(f"  ...{sink.count} events sent", file=sys.stderr)
            if deadline and time.time() > deadline:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        sink.flush()
        print(f"Sent {sink.count} events.", file=sys.stderr)


def run_scenario(name: str, sink: Sink, seed: int, tail_seconds: float = 12.0,
                 verbose: bool = True) -> None:
    """Play a scenario, then a few seconds of background traffic so Flink's
    event-time watermark moves past the scenario's last event (otherwise the
    windowed rules have no reason to emit yet)."""
    world = _world(seed)
    r = random.Random(f"{seed}:{name}")
    sc = SCENARIOS[name]
    for step in sc.steps(world, r):
        if step.delay:
            sink.deliver()  # send what we have before pausing, so Kafka sees real spacing
            events.CLOCK.sleep(step.delay)
        event = step.build()
        sink.send(step.topic, event, key=event["customer_id"])
        if verbose:
            detail = (f"${event['amount']:>8.2f} {event['merchant_category']:<13} "
                      f"{event['location']['city']}" if step.topic == "transactions" else
                      f"{'ok  ' if event['success'] else 'FAIL'} device={event['device_id']} "
                      f"{event['location']['city']}, {event['location']['country']}")
            print(f"  {event['timestamp']}  {step.topic:<13} {detail}")
    bg = background(world, random.Random(), anomaly_rate=0)
    t_end = events.CLOCK.now().timestamp() + tail_seconds
    while events.CLOCK.now().timestamp() < t_end:
        topic, event = next(bg)
        sink.send(topic, event, key=event["customer_id"])
        sink.deliver()
        events.CLOCK.sleep(0.5)
    sink.flush()


def cmd_scenario(args) -> None:
    if args.list or not args.name:
        for s in SCENARIOS.values():
            print(f"{s.name:<18} {s.customer_id:<16} {s.summary}")
        return
    if args.name not in SCENARIOS:
        raise SystemExit(f"unknown scenario {args.name!r}; try --list")
    sc = SCENARIOS[args.name]
    print(f"Scenario '{sc.name}' for {sc.customer_id}: {sc.summary}")
    run_scenario(sc.name, Sink(args.sink), args.seed)
    print(f"\nDone. Expected alerts: {', '.join(sc.expected_rules)}")
    print(f"Check: curl -s 'localhost:8010/alerts?customer_id={sc.customer_id}' | python3 -m json.tool")


def cmd_seed_demo(args) -> None:
    """Posts pre-computed events + alerts (captured from a real Flink run of
    all four scenarios) to the fraud API, re-timestamped to 'now'."""
    body = DEMO_SEED_FILE.read_bytes()
    req = urllib.request.Request(f"{args.api.rstrip('/')}/dev/seed", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except OSError as e:
        raise SystemExit(f"Could not reach the fraud API at {args.api} ({e}). Is it running? (make up)")
    print(f"Seeded {result['alerts']} alerts and {result['events']} events "
          f"for {len(result['customers'])} story customers.")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m datagen", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=reference.DEFAULT_SEED,
                    help="reference-data seed (keep the default: the lab docs assume it)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("personas").set_defaults(fn=cmd_personas)

    p = sub.add_parser("reference")
    p.add_argument("--out", default=str(REPO_ROOT / "data" / "reference"))
    p.set_defaults(fn=cmd_reference)

    p = sub.add_parser("load-reference")
    p.add_argument("--sink", default="kafka", choices=["kafka", "stdout"])
    p.set_defaults(fn=cmd_load_reference)

    p = sub.add_parser("simulate")
    p.add_argument("--rate", type=float, default=2.0, help="events per second")
    p.add_argument("--anomaly-rate", type=float, default=0.01)
    p.add_argument("--duration", type=float, default=0, help="seconds; 0 = until Ctrl-C")
    p.add_argument("--sink", default="kafka", choices=["kafka", "stdout"])
    p.set_defaults(fn=cmd_simulate)

    p = sub.add_parser("scenario")
    p.add_argument("name", nargs="?")
    p.add_argument("--list", action="store_true")
    p.add_argument("--sink", default="kafka", choices=["kafka", "stdout"])
    p.set_defaults(fn=cmd_scenario)

    p = sub.add_parser("seed-demo")
    p.add_argument("--api", default="http://localhost:8010")
    p.set_defaults(fn=cmd_seed_demo)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
