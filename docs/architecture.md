# Architecture

## Flow

1. A mock producer generates card transactions and login events into Kafka (`transactions`, `login-events`).
2. Flink continuously joins and evaluates the streams against deterministic rules: high transaction velocity, multiple failed logins, new/unusual device, impossible or unusual location, amount significantly above the customer's normal behavior.
3. Qualifying activity is published to `fraud-alerts`.
4. A FastAPI alert/case service consumes `fraud-alerts`, stores cases, and exposes them over a REST API.
5. watsonx Orchestrate coordinates three agents that investigate an alert via that API and other backend tool calls:
   - **Supervisor** — coordinates the investigation and delegates to the other two agents.
   - **Investigation** — retrieves the alert, transaction history, and customer/device context; explains the risk indicators.
   - **Policy & action** — retrieves relevant policy, recommends a permitted action, and prepares the case summary.
6. A human analyst reviews the recommendation and approves or rejects it.
7. On approval, a mock action API simulates the consequence (card lock, case creation, customer contact) and the case-action is recorded to `case-actions`.
8. (Stretch) Instana observes the distributed workflow end to end.

## Component responsibilities

| Component | Responsibility | Explicitly does NOT do |
|---|---|---|
| Kafka (Confluent Cloud) | Carries event streams | Business logic |
| Flink | Deterministic fraud-signal detection, stateful enrichment | Explanation, recommendation, natural-language output |
| FastAPI services | Mock enterprise systems; expose clean tools to Orchestrate | Direct Kafka consumption by agents (agents call APIs, not topics) |
| watsonx Orchestrate | Multi-agent coordination and analyst-facing interaction | Authorizing/declining transactions; consuming Kafka directly |
| Human analyst | Approves or rejects the recommended action | — |
| OpenShift (stretch) | Hosts the FastAPI services and any consumers | Not the agent brain or streaming engine |
| OpenShift AI (stretch) | Serves a fraud-scoring model if one is added | Not required for MVP — no model is served without a legitimate purpose |
| Instana (stretch) | Distributed tracing, service health, latency | Added last, after core services are deployed |

## Design principle

Agents investigate and recommend. They never authorize or decline a financial transaction. That decision is either fully deterministic (Flink rule fired → alert created) or requires explicit human approval (action executed). This separation is the core credibility point of the system and should not be diluted as scope grows.

## Kafka topics

- `transactions` — card transaction events
- `login-events` — authentication events
- `fraud-alerts` — alerts produced by Flink rules
- `case-actions` — case/action lifecycle events (recommended → approved/rejected → executed)

Additional topics (`customer-updates`, `analyst-feedback`) are added only if a concrete need arises — not preemptively.

## Open items / blockers

See the project's Day 1 plan for current blockers (Orchestrate custom-tool capability, Orchestrate-to-local reachability, Confluent Flink entitlement). Update this section as they resolve.
