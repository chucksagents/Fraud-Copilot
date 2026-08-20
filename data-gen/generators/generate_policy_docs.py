"""
Write the fraud-response policy documents the "policy & action" agent will
retrieve from. These are static, hand-authored text (not randomized) —
this script just places them under data-gen/fixtures/policies/ so the whole
fixture set can be regenerated with one command.

Usage: python3 generate_policy_docs.py
"""

from __future__ import annotations

from .common import FIXTURES_DIR

POLICIES = {
    "policy_high_velocity.md": """# Policy: High Transaction Velocity

**Rule:** `high_velocity` — multiple transactions on the same card/account
within a short window, exceeding the customer's normal daily transaction
count.

## Permitted actions by severity

- **low** — no automatic action. Log for analyst awareness only.
- **medium** — recommend `contact_customer` to confirm the activity.
- **high** — recommend `card_lock` and `contact_customer`. Escalate if the
  customer cannot be reached within 30 minutes.

## Notes for the investigating agent

Card-testing fraud (small, rapid authorizations against a stolen card
number) is the most common cause. Check whether transaction amounts are
unusually small and merchants are unrelated to the customer's typical
categories — that combination raises confidence this is fraud rather than
a legitimate shopping spree.
""",
    "policy_multiple_failed_logins.md": """# Policy: Multiple Failed Logins

**Rule:** `multiple_failed_logins` — several failed authentication attempts
followed by a success, or an unresolved string of failures.

## Permitted actions by severity

- **low** (2-3 failures, then success from a known device) — no action.
- **medium** (4+ failures, then success from a known device, or 2-3
  failures from a new device) — recommend `contact_customer`.
- **high** (4+ failures then success from a new/unusual device, or
  failures followed by a high-value transaction) — recommend
  `card_lock` and `escalate`.

## Notes for the investigating agent

Distinguish a customer who mistyped a password from a credential-stuffing
attempt: check whether the device and location match the customer's
history. A new device *and* a new location together is a strong signal.
""",
    "policy_new_or_unusual_device.md": """# Policy: New or Unusual Device

**Rule:** `new_or_unusual_device` — activity from a device not previously
associated with the customer.

## Permitted actions by severity

- **low** — a new device with no prior failed logins and a transaction
  consistent with the customer's normal spend: no action, mark device as
  seen.
- **medium** — new device plus a transaction above the customer's typical
  amount: recommend `contact_customer`.
- **high** — new device, unusual location, and an above-average
  transaction together: recommend `card_lock` and `escalate`.

## Notes for the investigating agent

A new device alone is common and often legitimate (new phone, new
browser). Only escalate when it co-occurs with another signal — amount,
location, or login failures.
""",
    "policy_impossible_travel.md": """# Policy: Impossible Travel

**Rule:** `impossible_travel` — two authenticated events for the same
customer from locations that are not physically reachable within the
elapsed time between them.

## Permitted actions by severity

- **medium** (borderline distance/time, plausible edge case such as a VPN)
  — recommend `contact_customer`.
- **high** (clearly impossible, e.g. two countries within minutes) —
  recommend `card_lock` and `escalate`. This is one of the strongest
  single-signal indicators of account takeover.

## Notes for the investigating agent

Check whether one of the two locations matches a device/IP the customer
has used before via VPN or travel. If neither location has any prior
history for this customer, confidence in fraud is high.
""",
    "policy_amount_anomaly.md": """# Policy: Amount Anomaly

**Rule:** `amount_anomaly` — a transaction amount significantly above the
customer's historical average for that merchant category (see
`customer_behavior.json`, typically >5x average or >3 standard
deviations).

## Permitted actions by severity

- **low** (3-5x average, familiar merchant category) — no action.
- **medium** (5-10x average, or unfamiliar merchant category) — recommend
  `contact_customer`.
- **high** (>10x average, unfamiliar merchant category, and/or combined
  with another signal such as a new device) — recommend `card_lock` and
  `contact_customer`; escalate if unreachable.

## Notes for the investigating agent

Large legitimate purchases happen (a new appliance, a flight). Weigh this
rule much more heavily when it co-occurs with a device, login, or location
signal than when it fires alone.
""",
    "policy_escalation.md": """# Policy: Escalation and Human Approval

**This policy overrides all others.**

No agent may execute `card_lock`, `contact_customer`, or any other
consequential action on its own authority. Every recommendation produced
by the policy & action agent has status `recommended` and must be reviewed
by a human analyst, who sets status to `approved` or `rejected` before the
action API executes anything.

`escalate` means: flag the case for priority human review, do not attempt
further automated investigation steps, and do not suggest a specific
action beyond escalation itself.

Agents should always state their confidence and the specific evidence
behind a recommendation so the analyst can make an informed decision
quickly.
""",
}


def main() -> None:
    policies_dir = FIXTURES_DIR / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in POLICIES.items():
        (policies_dir / filename).write_text(content)
    print(f"Wrote {len(POLICIES)} policy documents to {policies_dir}")


if __name__ == "__main__":
    main()
