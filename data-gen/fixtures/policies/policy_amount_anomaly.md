# Policy: Amount Anomaly

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
