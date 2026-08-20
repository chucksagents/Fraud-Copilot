# Producers

Mock producers that emit `transactions` and `login-events`, validated
against the schemas in `docs/schemas/` before send. Each producer mostly
emits normal, baseline-consistent traffic (sampled from
`data-gen/fixtures/customer_behavior.json`) and injects a configurable
fraction of anomalous patterns matching the five Flink rules planned for
Day 2: high velocity, multiple failed logins, new/unusual device,
impossible travel, and amount anomaly.

Requires fixtures to exist first: `python3 data-gen/generators/generate_all.py`.

## Install

```bash
cd streaming/producers
pip install -r requirements.txt
```

`confluent-kafka` is intentionally not in the base requirements — only
needed for `--sink kafka`. Install it separately once Confluent Cloud (or
local Kafka) access is confirmed.

## Usage

```bash
# Print events to stdout (no Kafka needed) — good for eyeballing output
python3 transaction_producer.py --sink stdout --count 20
python3 login_event_producer.py --sink stdout --count 20

# Write to a local .jsonl file under data-gen/fixtures/
python3 transaction_producer.py --sink file --count 1000

# Send to Kafka (local docker-compose stack or Confluent Cloud, per infra/.env)
python3 transaction_producer.py --sink kafka --count 1000 --rate 5
python3 login_event_producer.py --sink kafka --count 1000 --rate 5
```

Useful flags: `--anomaly-rate` / `--burst-rate` (transactions),
`--failed-burst-rate` / `--new-device-rate` / `--travel-rate` (logins),
`--seed` for reproducible runs, `--rate` to pace events/sec (0 = as fast as
possible).

## Smoke test

`tests/test_smoke.py` runs both producers' full code path (including
anomaly injection) and validates every emitted event against its schema,
without needing Kafka:

```bash
python3 tests/test_smoke.py
```
