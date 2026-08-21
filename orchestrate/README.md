# orchestrate/

The watsonx Orchestrate side of the demo: a custom tool that calls
`services/alert-api`, and a native agent that uses it to investigate a
fraud alert and recommend one action for a human to approve.

Resolves blockers #1 and #2 from the Day 1 plan:

- **Custom tool/agent support**: confirmed against IBM's official ADK
  docs (developer.watson-orchestrate.ibm.com) -- the ADK fully supports
  custom Python tools (`@tool`-decorated functions calling out to any
  REST API) and native custom agents (YAML/JSON/Python, not just
  prebuilt skills). Not a blocker.
- **Reachability**: running against watsonx Orchestrate **Developer
  Edition** (local Docker -- `orchestrate env list` shows this as
  `local`, http://localhost:4321), not the SaaS instance. A tool running
  there can reach the alert API on your Mac directly via
  `host.docker.internal:8000` -- no tunnel needed. If you switch to SaaS
  later (e.g. `fin-rm-env`), see the tunnel fallback in
  `tools/alert_api_tools.py`'s docstring -- SaaS can't reach `localhost`
  or `host.docker.internal` at all.

## Files

```
tools/
  alert_api_tools.py   get_alert, list_open_alerts, recommend_case_action
  requirements.txt     requests
agents/
  fraud_investigation_agent.yaml
```

## Setup, in order

1. **Confirm Developer Edition is actually running**, not just
   registered as an environment:

   ```bash
   docker ps          # should show watsonx Orchestrate's containers
   ```

   If nothing's running:

   ```bash
   orchestrate server start -e <path to your .env file>
   ```

   (Use whatever `.env` file you set up for Developer Edition previously
   -- it holds the watsonx.ai credentials the local server itself needs,
   separate from `infra/.env`, which is Kafka-only.)

2. **Start the alert API bound to all interfaces**, not just
   `127.0.0.1` -- the container needs to reach in from outside plain
   `localhost`:

   ```bash
   cd services/alert-api
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. **Confirm `local` is the active environment:**

   ```bash
   orchestrate env list   # local should show (active)
   orchestrate env activate local   # if it isn't
   ```

4. **Import the tool and the agent:**

   ```bash
   orchestrate tools import -k python -f orchestrate/tools/alert_api_tools.py \
     -r orchestrate/tools/requirements.txt

   orchestrate agents import -f orchestrate/agents/fraud_investigation_agent.yaml
   ```

5. **Test it:**

   ```bash
   orchestrate chat start
   ```

   Grab an `alert_id` from `GET /alerts` (or just ask the agent to list
   open alerts) and ask it to investigate that alert.

## If `host.docker.internal` doesn't resolve

Fall back to your Mac's LAN IP: `ipconfig getifaddr en0` (or `en1`), and
use that instead of `host.docker.internal` in
`tools/alert_api_tools.py`'s `ALERT_API_BASE_URL`, then re-run step 4's
`orchestrate tools import`.

## Switching to SaaS later

Unlike Developer Edition, this needs a public URL every time --
`host.docker.internal` doesn't exist for a cloud-hosted instance. See
the "Reachability" docstring in `tools/alert_api_tools.py` for the
`cloudflared` tunnel approach, and re-import the tool each time the
tunnel restarts (it hands out a new random URL every run).

## Deliberately not built yet

`customer-context-api` (Day 1 plan) is still just a stub README --
`fraud_investigation_agent` currently reasons only from `evidence` on
the alert itself, not customer history or policy docs. Open decision
(Day 3 handoff item #4): whether alert evidence alone is enough for the
demo, or whether the agent needs the policy markdown in
`data-gen/fixtures/policies/` (one per rule) folded in, e.g. as a
knowledge base or a fourth tool.
