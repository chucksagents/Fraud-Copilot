# Policy: High Transaction Velocity

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
