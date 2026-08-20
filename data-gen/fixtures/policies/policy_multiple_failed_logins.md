# Policy: Multiple Failed Logins

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
