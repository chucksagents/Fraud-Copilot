# Policy: Impossible Travel

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
