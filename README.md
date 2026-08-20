# Fraud Investigation & Response System

Real-time fraud investigation and analyst copilot. Deterministic streaming rules (Kafka + Flink) detect suspicious activity; a small watsonx Orchestrate multi-agent workflow investigates, explains, and recommends a response; a human analyst approves any consequential action.

This is a personal enablement project demonstrating an end-to-end Forward Deployed Engineer workflow: real-time data, multi-agent orchestration, containerized APIs, and (as a stretch) enterprise deployment and observability.

## Why this design

LLM agents never authorize or decline a financial action directly. Flink rules (or, as a stretch, a served fraud-scoring model) create the alert deterministically. Agents investigate the alert, gather context, explain the risk indicators, consult policy, and recommend an action — a human analyst approves or rejects before anything executes.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full data flow and component responsibilities.

```
Producers → Kafka (transactions, login-events) → Flink (rules) → fraud-alerts topic
    → Alert/Case API (FastAPI) → watsonx Orchestrate agents → Analyst approval
    → Case-action API → mock card-lock / case action
```

## Repository layout

```
fraud-copilot/
  docs/                      architecture notes and event schemas
  data-gen/                  synthetic reference data + generators
  streaming/                 Kafka producers and Flink SQL rules
  services/                  FastAPI services (alert/case API, context API, action API)
  orchestrate/               watsonx Orchestrate agent and tool definitions
  infra/                     docker-compose, env config, OpenShift manifests (later)
  tests/                     unit and integration tests
```

## Status

MVP in progress. See the project's Day 1 architecture and plan doc for current scope, blockers, and checklist. OpenShift, OpenShift AI, and Instana are intentionally deferred until the local vertical slice works end-to-end.

## Local setup (placeholder — filled in as services are built)

```bash
cp infra/.env.example infra/.env
docker compose -f infra/docker-compose.yml up -d
```

## MVP scope

- Synthetic transaction, login, customer, device, and merchant data
- Kafka topics: `transactions`, `login-events`, `fraud-alerts`, `case-actions`
- Three to five Flink fraud rules (velocity, failed logins, new device, unusual location, amount anomaly)
- Fraud alert/case FastAPI service
- ~3 watsonx Orchestrate agents (supervisor, investigation, policy/action)
- Human approval gate before any consequential action
- Simulated card lock / case creation
- Local containerization via docker-compose

Stretch, in priority order: OpenShift deployment, Instana instrumentation, fraud model served via OpenShift AI, policy RAG, watsonx.governance evidence, analyst-feedback events.
