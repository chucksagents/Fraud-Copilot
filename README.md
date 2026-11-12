# Fraud Investigation & Response System

Real-time fraud investigation and analyst copilot. Deterministic streaming rules (Kafka + Flink) detect suspicious activity; a small watsonx Orchestrate agent investigates, explains, and recommends a response; a human analyst approves any consequential action.

This is a personal enablement project demonstrating an end-to-end Forward Deployed Engineer workflow: real-time data, agentic investigation, containerized APIs, and (as a stretch) enterprise deployment and observability.

## Why this design

LLM agents never authorize or decline a financial action directly. Flink rules (or, as a stretch, a served fraud-scoring model) create the alert deterministically. The agent investigates the alert, gathers context, explains the risk indicators, and recommends an action — a human analyst approves or rejects before anything executes. The `recommend_case_action` tool enforces this in code, not just in the agent's instructions: it can only ever write `status="recommended"`.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full data flow and component responsibilities.

```
Producers → Kafka (transactions, login-events) → Flink (rules) → fraud-alerts topic
    → Alert/Case API (FastAPI) → watsonx Orchestrate agent → Analyst approval
    → POST /cases/{case_id}/actions → case-actions topic
```

## Repository layout

```
fraud-copilot/
  docs/                      architecture notes and event schemas
  data-gen/                  synthetic reference data + generators
  streaming/                 Kafka producers and Flink SQL rules
  services/                  FastAPI services (alert/case API; context + action APIs are stubs)
  orchestrate/               watsonx Orchestrate agent and tool definitions
  infra/                     env config (infra/.env — Kafka credentials, gitignored) + infra/openshift/ manifests
  tests/                     unit and integration tests
```

## Status

Confirmed working end-to-end as of 2026-08-21: producers → Confluent Cloud → all 5 Flink rules → alert/case API → SQLite, and a working watsonx Orchestrate agent that calls the alert API live via `orchestrate chat start`. `customer-context-api` and `action-api` are still unbuilt stubs — the investigation agent currently reasons from alert `evidence` alone (plus a customer's alert history via `get_alerts_by_customer`), not policy docs or deeper customer context.

`alert-api` is live on OpenShift as of 2026-08-24 — deployed to a Red Hat Developer Sandbox project via [`infra/openshift/`](infra/openshift/README.md), serving real alert data over its Route (`GET /health` and `GET /alerts` both verified working). `orchestrate/tools/alert_api_tools.py`'s `ALERT_API_BASE_URL` now points at that Route instead of a `cloudflared` tunnel, so the tunnel is no longer needed for this to work. Getting there surfaced three Sandbox-specific gotchas now documented in `infra/openshift/README.md` and inline in `deployment.yaml`/`config.py`: Sandbox's SCC rejects a hardcoded `fsGroup: 0` (must be left unset instead), `oc set image-lookup` doesn't actually resolve the image on this cluster (an `image.openshift.io/triggers` annotation does instead), and `services/alert-api/app/config.py`'s `REPO_ROOT` computation assumed the local directory depth and crashed on the container's shallower one (now falls back gracefully). OpenShift AI and Instana remain intentionally deferred.

## Local setup (end-to-end)

Each of these has a more detailed README in its own directory — this section is the order that actually works, start to finish. `coneill1213`'s `obsidian-learning-vault` has a `watsonx Orchestrate.md` note with the full debugging trail behind some of the gotchas called out below.

### 0. Prerequisites

- A Confluent Cloud account with a cluster, an API key/secret for it, and a **Flink compute pool enabled** (a separate entitlement from plain Kafka access — confirm this before relying on it).
- Docker Desktop, and either a watsonx Orchestrate SaaS instance or the ADK's Developer Edition set up locally (`pip install ibm-watsonx-orchestrate` gives you the `orchestrate` CLI).
- Python 3.11+.
- `cloudflared` (`brew install cloudflared`) — used later to expose the alert API to Orchestrate. (Optional if you deploy `alert-api` to OpenShift instead — see step 8a.)

### 1. Kafka / Confluent Cloud

1. In the Confluent Cloud console, create 4 topics: `transactions`, `login-events`, `fraud-alerts`, `case-actions`.
2. `cp infra/.env.example infra/.env` and fill in `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_API_KEY`, `KAFKA_API_SECRET`, and set `KAFKA_SECURITY_PROTOCOL=SASL_SSL`. Never commit this file (already gitignored).

### 2. Generate reference data

```bash
cd data-gen/generators
python3 generate_all.py   # writes into data-gen/fixtures/ (gitignored)
```

### 3. Submit the Flink SQL rules

Full detail and gotchas in [`streaming/flink-sql/README.md`](streaming/flink-sql/README.md) — the short version: in the Confluent Cloud Flink SQL workspace, run these one at a time, in this order:

1. `00_create_fraud_alerts_table.sql` — **once**. Delete any existing `fraud-alerts` topic/schema first if you're re-running this (Flink's schema inference on this table has bitten us twice; this file hand-declares it correctly).
2. `amount_anomaly.sql`
3. `high_velocity.sql`
4. `multiple_failed_logins.sql`
5. `new_or_unusual_device.sql`
6. `impossible_travel.sql`

### 4. Install producer + alert API dependencies

```bash
python3 -m venv .env && source .env/bin/activate   # or your preferred venv approach
cd streaming/producers && pip install -r requirements.txt && pip install "confluent-kafka>=2.4" && cd ../..
cd services/alert-api && pip install -r requirements.txt && cd ../..
```

Quote the version specifier — `confluent-kafka>=2.4` unquoted gets mangled by zsh's redirect parsing and silently fails to install.

### 5. Start the alert API

```bash
cd services/alert-api
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Port **8010, not 8000** — port 8000 is a known macOS/Docker-Desktop/Lima landmine (see `streaming/flink-sql/README.md`'s sibling gotchas doc, or the vault note) that produced confusing, unrelated responses when we tried it. `infra/.env.example`'s `ALERT_API_PORT=8000` is aspirational only — nothing in the code actually reads it; the port is whatever you pass `uvicorn` directly. (This Mac-local port landmine doesn't apply inside an OpenShift pod — `infra/openshift/`'s manifests use container port 8000 with no conflict.)

Leave this running. On startup it should log `subscribed to fraud-alerts (group=alert-api)` and `fraud-alerts consumer thread started`.

### 6. Send test data

In separate terminals, from `streaming/producers/` (full flag reference in that directory's README):

```bash
# Baseline first -- amount_anomaly needs trailing history before it can fire
python3 transaction_producer.py --sink kafka --count 1000 --anomaly-rate 0 --burst-rate 0 --rate 20
python3 transaction_producer.py --sink kafka --count 300 --anomaly-rate 0.3 --burst-rate 0.2 --rate 10
python3 login_event_producer.py --sink kafka --count 300 --failed-burst-rate 0.2 --new-device-rate 0.2 --travel-rate 0.1 --rate 10
```

### 7. Verify the pipeline

```bash
curl http://localhost:8010/alerts | python3 -m json.tool
curl "http://localhost:8010/alerts?customer_id=<some_customer_id>"
```

You should see alerts across all 5 `rule_triggered` types, each with a populated `case_id` (that comes from the alert API auto-opening a `Case` on ingest — Flink itself never writes `case_id`).

### 8. watsonx Orchestrate setup

Full detail in [`orchestrate/README.md`](orchestrate/README.md). Using Developer Edition (local):

```bash
# One-time: create orchestrate/dev-edition.env with WO_INSTANCE + WO_API_KEY
# (get these from your watsonx Orchestrate account: profile icon -> Settings -> API details)
orchestrate server start -e orchestrate/dev-edition.env --accept-terms-and-conditions
```

Confirm it's actually up (not just that `orchestrate env list` shows `local` as active — that's only a config pointer): `curl http://localhost:4321` should return a real `uvicorn` response.

Expose the alert API to Orchestrate — `host.docker.internal` and `host.lima.internal` both failed for us for reasons never fully diagnosed, so:

```bash
cloudflared tunnel --url http://localhost:8010
```

Copy the printed `https://*.trycloudflare.com` URL into `ALERT_API_BASE_URL` at the top of `orchestrate/tools/alert_api_tools.py`, then:

```bash
orchestrate tools import -k python -f orchestrate/tools/alert_api_tools.py -r orchestrate/tools/requirements.txt
orchestrate agents import -f orchestrate/agents/fraud_investigation_agent.yaml
orchestrate chat start
```

The tunnel hands out a new URL every time it restarts — re-run the `tools import` step whenever that happens.

#### 8a. Or skip the tunnel: deploy `alert-api` to OpenShift instead

[`infra/openshift/README.md`](infra/openshift/README.md) walks through deploying `alert-api` to a free Red Hat Developer Sandbox project (manifests are in `infra/openshift/`; live there as of 2026-08-24). Its Route gives you a stable public HTTPS URL that never changes on restart — `orchestrate/tools/alert_api_tools.py`'s `ALERT_API_BASE_URL` already points at it, so `cloudflared` is no longer needed. Works the same way whether Orchestrate is Developer Edition or SaaS.

### 9. Try it

In the chat: "show 20 most recent alerts", or give it a specific `alert_id`/`customer_id` from step 7's output and ask it to investigate.

## MVP scope

- Synthetic transaction, login, customer, device, and merchant data
- Kafka topics: `transactions`, `login-events`, `fraud-alerts`, `case-actions`
- 5 Flink fraud rules (velocity, failed logins, new device, impossible travel, amount anomaly)
- Fraud alert/case FastAPI service
- 1 watsonx Orchestrate investigation agent (get_alert, list_open_alerts, get_alerts_by_customer, recommend_case_action)
- Human approval gate before any consequential action
- Local containerization via Developer Edition + Docker

Stretch, in priority order: `customer-context-api` (history, policy docs, behavior baseline), OpenShift deployment (scaffolded, see `infra/openshift/`, not yet deployed), Instana instrumentation, fraud model served via OpenShift AI, policy RAG, watsonx.governance evidence, analyst-feedback events.
