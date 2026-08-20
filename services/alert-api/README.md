# Fraud Alert & Case API

FastAPI service that turns Flink's `fraud-alerts` stream into a queryable
alert/case API for Orchestrate agents and analysts.

- A background thread consumes `fraud-alerts` continuously and persists
  each alert into SQLite, auto-opening a `Case` for it.
- `GET /alerts` -- list alerts (filterable by `rule_triggered`, `severity`;
  paginated with `limit`/`offset`), newest-ingested first.
- `GET /alerts/{alert_id}` -- a single alert, with its `case_id`.
- `POST /cases/{case_id}/actions` -- record a case action (`card_lock`,
  `contact_customer`, `no_action`, `escalate`) and republish it to the
  `case-actions` topic.

## Run it locally

```bash
cd services/alert-api
pip install -r requirements.txt
```

Make sure `infra/.env` exists and is filled in (copy from
`infra/.env.example` if you haven't already) -- same file the producers and
Flink already use, nothing new to configure beyond the credentials you have.

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run it from inside `services/alert-api/` (matching the Dockerfile's
`WORKDIR /app`) -- `ALERT_API_DB_URL=sqlite:///./alerts.db` is a relative
path, so the SQLite file lands next to wherever you launched uvicorn from.

On startup you should see log lines like:

```
INFO:alert_api.kafka_consumer:subscribed to fraud-alerts (group=alert-api)
INFO:alert_api:fraud-alerts consumer thread started
```

Since the consumer group starts from `auto.offset.reset=earliest` the first
time it runs, it will immediately backfill every alert already sitting in
the topic -- including the ones from your earlier producer test runs.

## Try it

Interactive API docs (Swagger UI) are auto-served at
`http://localhost:8000/docs` -- easiest way to poke at this without curl.

```bash
# List everything ingested so far
curl http://localhost:8000/alerts | python3 -m json.tool

# Filter to one rule
curl "http://localhost:8000/alerts?rule_triggered=multiple_failed_logins"

# Grab a case_id from one of the above, then act on it
curl -X POST http://localhost:8000/cases/<case_id>/actions \
  -H "Content-Type: application/json" \
  -d '{"action_type": "card_lock", "status": "executed", "actor": "investigation_agent", "notes": "auto-locked per policy"}'
```

A `POST` returns `201` and persists the action even if Kafka is
unreachable -- it just logs the publish failure loudly rather than losing
the analyst/agent's decision. Worth keeping an eye on those logs if
`case-actions` messages seem to be going missing downstream.

## Design notes / where this cuts corners for a demo

- **One case per alert, always.** A `Case` is auto-opened the instant an
  alert is ingested (1:1). `case_id` is separate from `alert_id` on purpose
  so a future version could merge several related alerts into one case
  without an API change -- but nothing does that merging today.
- **`fraud-alerts` decoding skips real schema-registry deserialization.**
  Confluent's `json-registry` format frames each message as
  `[magic byte][4-byte schema id][JSON payload]`. `kafka_consumer.py` just
  strips that 5-byte header rather than pulling in a
  `SchemaRegistryClient` + `JSONDeserializer` -- simpler, and fine since we
  don't need schema validation on read. If that ever gets fragile, that's
  the file to revisit.
- **`case-actions` is published as plain JSON**, no wire-format framing --
  unlike `fraud-alerts`, nothing currently reads this topic through a Flink
  table with `'value.format' = 'json-registry'` declared, so there's no
  registered schema to conform to yet. If you add one later, switch
  `kafka_producer.py` to a real `JSONSerializer`.
- **Alerts are immutable once ingested** -- the consumer skips any
  `alert_id` it's already seen rather than updating it. Matches the
  fraud-alert schema's intent (Flink produces each alert once).
- **The "executed closes the case" rule in `main.py`** is a one-line
  placeholder heuristic, not a real state machine. Easy to find (search
  for `body.status == "executed"`) and replace once you know what case
  lifecycle you actually want.
- **SQLite, single file, no migrations.** `Base.metadata.create_all()` runs
  on every startup, which only ever adds missing tables -- if you change a
  model's columns later you'll need to delete `alerts.db` (or add real
  migrations, e.g. Alembic) rather than expecting it to alter existing
  tables.

## Files

```
app/
  main.py            FastAPI app, lifespan (starts/stops the consumer thread), routes
  config.py          env loading + Kafka conf builder (mirrors streaming/producers/common.py)
  db.py              SQLAlchemy engine/session
  models.py          Alert, Case, CaseAction ORM models
  schemas.py         Pydantic request/response models
  kafka_consumer.py  background thread: fraud-alerts -> Alert + Case rows
  kafka_producer.py  publishes case actions to case-actions
```

## Next up

Per the architecture doc, this is the piece watsonx Orchestrate's agents
call as a custom tool -- point `WXO_ALERT_API_BASE_URL` (in `infra/.env`)
at wherever this is reachable from Orchestrate (a tunnel, or later an
OpenShift Route) once you're ready to wire that up.
