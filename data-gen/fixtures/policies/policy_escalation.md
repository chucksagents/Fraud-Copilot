# Policy: Escalation and Human Approval

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
