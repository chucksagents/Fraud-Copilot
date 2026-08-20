# Tests

Unit tests for producers, Flink rule logic (where testable outside the cluster), and the FastAPI services. Integration tests for the vertical slice: produce a qualifying event → alert appears in the API → agent can retrieve and explain it.

## `test_smoke.py` (Day 1)

No Kafka, no Orchestrate, no network required. Generates fixtures if
missing, checks referential integrity (devices/behavior profiles reference
real customers, etc.), then runs both producers' full generation path —
including every anomaly-injection branch (velocity burst, amount anomaly,
failed-login burst, new device, impossible travel) — validating every
emitted event against its JSON schema.

```bash
python3 tests/test_smoke.py
```

Exit code 0 = pass, 1 = fail with a list of what broke.
