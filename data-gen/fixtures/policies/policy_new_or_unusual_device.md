# Policy: New or Unusual Device

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
