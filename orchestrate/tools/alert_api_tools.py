"""
Custom Python tools that let a watsonx Orchestrate agent talk to the
fraud alert/case API (services/alert-api).

Covers blocker #3 from the Day 1 plan / Day 3 handoff: yes, the ADK
supports custom Python tools (confirmed against IBM's official ADK docs,
2026-08) -- this is the actual implementation of that.

## Reachability (the other open blocker)

Using watsonx Orchestrate Developer Edition (local Docker, `orchestrate
env list` shows it as `local` / http://localhost:4321) rather than the
SaaS instance -- this tool file runs inside a container on your own Mac,
which can reach the alert API on your host machine via the standard
Docker Desktop hostname `host.docker.internal`, no tunnel required.
`host.docker.internal:8000` should just work as long as:

1. The Developer Edition server is actually running (`docker ps` should
   show its containers; if not, `orchestrate server start -e <env-file>`).
2. `services/alert-api` is running on the host at port 8000 (not just
   bound to `127.0.0.1` -- `--host 0.0.0.0` in the uvicorn command, per
   its README, matters here since the container reaches in from outside
   localhost).

If `host.docker.internal` doesn't resolve for some reason, fall back to
your Mac's LAN IP instead (`ipconfig getifaddr en0`, or `en1` if you're
on Wi-Fi via a different interface) and use that in place of
`host.docker.internal` below.

If you switch to the SaaS environment later (`fin-rm-env` or a fresh
`orchestrate env add`), none of the above applies -- SaaS can't reach
`localhost` or `host.docker.internal` at all, and you'd need a public
URL instead (a `cloudflared` quick tunnel: `brew install cloudflared`,
then `cloudflared tunnel --url http://localhost:8000`, pasting the
resulting `https://*.trycloudflare.com` URL below and re-running
`orchestrate tools import` every time the tunnel restarts, since it
hands out a new random URL each run).

**Longer-term fix for the tunnel's stale-URL problem**: once
`services/alert-api` is deployed to OpenShift (see
`infra/openshift/README.md`), swap ALERT_API_BASE_URL below for that
deployment's Route host instead. A Route is a stable public HTTPS
endpoint -- it works from Developer Edition *and* SaaS unchanged, doesn't
regenerate on restart the way the tunnel does, and you can stop running
`cloudflared` entirely. Re-run `orchestrate tools import` once after
switching, same as any other edit to this file.

Kept as a plain constant rather than an Orchestrate "connection" (which
is really for per-app credentials, e.g. API keys/bearer tokens) since
this API has no auth yet -- straightforward to swap for
`orchestrate connections` later if that changes.
"""

from __future__ import annotations

import requests

from ibm_watsonx_orchestrate.agent_builder.tools import tool

# --- EDIT ME only if this Route ever changes ---
# `alert-api` is deployed to Red Hat Developer Sandbox as of 2026-08-24 (see
# infra/openshift/README.md) -- this is that Deployment's Route host, a
# stable public HTTPS endpoint. Unlike the old cloudflared tunnel this used
# to point at, it does NOT change on restart, so there's no more re-running
# `orchestrate tools import` every time something bounces. Only re-import if
# this literal URL ever changes (e.g. the Sandbox project is recreated).
#
#   oc get route alert-api -o jsonpath='{.spec.host}{"\n"}'
#
# would reprint it if you ever need to double check.
ALERT_API_BASE_URL = "https://alert-api-charlie-oneill-dev.apps.rm2.thpm.p1.openshiftapps.com"

_TIMEOUT_SECONDS = 15


@tool
def get_alert(alert_id: str) -> dict:
    """Fetch a single fraud alert by its alert_id, including the case_id
    of the case that was auto-opened for it and the rule-specific
    `evidence` the Flink rule produced (e.g. the anomalous amount and the
    customer's trailing average, or the two login locations and the time
    between them). Use this before recommending any action so the
    recommendation is grounded in the actual evidence rather than
    guessed.

    Returns fields: alert_id, generated_at, customer_id, account_id,
    rule_triggered, severity, related_event_ids, evidence, status,
    case_id.

    Raises an error (surfaced to you as a tool error) if the alert_id
    doesn't exist -- double-check it against list_open_alerts if unsure.
    """
    resp = requests.get(
        f"{ALERT_API_BASE_URL}/alerts/{alert_id}", timeout=_TIMEOUT_SECONDS
    )
    resp.raise_for_status()
    return resp.json()


@tool
def list_open_alerts(rule_triggered: str = "", severity: str = "", limit: int = 20) -> list:
    """List fraud alerts, newest first, so you (or the person you're
    helping) can see what's waiting on investigation. Optionally filter
    by rule_triggered (e.g. "amount_anomaly", "high_velocity",
    "multiple_failed_logins", "new_or_unusual_device",
    "impossible_travel") and/or severity ("low", "medium", "high").
    Leave a filter as an empty string to not apply it.

    Returns a list of the same alert objects get_alert returns.
    """
    params = {"limit": limit}
    if rule_triggered:
        params["rule_triggered"] = rule_triggered
    if severity:
        params["severity"] = severity
    resp = requests.get(
        f"{ALERT_API_BASE_URL}/alerts", params=params, timeout=_TIMEOUT_SECONDS
    )
    resp.raise_for_status()
    return resp.json()


@tool
def get_alerts_by_customer(customer_id: str, limit: int = 20) -> list:
    """Look up every fraud alert on record for one customer, newest
    first. Use this when you're given a customer_id rather than a
    specific alert_id -- e.g. "what's going on with customer
    cust_9c5c8c181993" -- to see their full alert history before
    focusing on any one alert with get_alert.

    Returns a list of the same alert objects get_alert returns (each
    including its own case_id). Returns an empty list, not an error, if
    the customer has no alerts on record.
    """
    resp = requests.get(
        f"{ALERT_API_BASE_URL}/alerts",
        params={"customer_id": customer_id, "limit": limit},
        timeout=_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()


@tool
def recommend_case_action(case_id: str, action_type: str, notes: str = "") -> dict:
    """Record your investigation's recommended action on a case. This
    always records status="recommended" -- per the system's design, an
    agent recommends and a human approves; do not call this in a way
    that marks an action "executed", and do not tell the user the action
    has been taken. Frame your response as a recommendation awaiting
    approval.

    action_type must be exactly one of: "card_lock", "contact_customer",
    "no_action", "escalate".

    notes should be a short (1-3 sentence) plain-language justification
    tying the recommendation back to the alert's evidence and the
    relevant fraud policy, e.g. "Transaction amount is 9x the customer's
    30-day average with no prior travel notice on file; recommend
    locking the card pending contact."

    Returns the created case-action record (id, case_id, alert_id,
    action_type, status, actor, timestamp, notes). Raises an error if
    case_id doesn't exist -- get it from get_alert's `case_id` field, not
    from the alert_id.
    """
    resp = requests.post(
        f"{ALERT_API_BASE_URL}/cases/{case_id}/actions",
        json={
            "action_type": action_type,
            "status": "recommended",
            "actor": "fraud_investigation_agent",
            "notes": notes or None,
        },
        timeout=_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()
