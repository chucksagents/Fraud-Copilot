# Generators

Scripts that produce static synthetic reference data (not streamed) into
`data-gen/fixtures/` (gitignored — regenerate locally with the command
below rather than committing generated data):

- `generate_customers.py` — customers, accounts, cards
- `generate_devices.py` — trusted devices per customer, plus an untrusted
  device pool for new-device/account-takeover scenarios
- `generate_merchants.py` — merchants, category, risk level
- `generate_customer_behavior.py` — per-customer baseline (avg spend,
  typical merchant categories, typical login hours) that producers sample
  from and that rules/agents treat as "normal"
- `generate_fraud_cases.py` — a small history of previously resolved fraud
  cases, for agent precedent and the customer-context API
- `generate_policy_docs.py` — static fraud-response policy documents under
  `data-gen/fixtures/policies/`, for the policy & action agent

All data is synthetic — no real customer information.

## Usage

```bash
cd data-gen/generators
python3 generate_all.py                # defaults: 200 customers, 60 merchants, 40 fraud cases
python3 generate_all.py --customers 50 --merchants 20 --fraud-cases 10 --seed 42
```

Or run an individual generator (note the dependency order — customers
before devices/behavior/fraud-cases):

```bash
python3 generate_customers.py --count 200
python3 generate_devices.py
python3 generate_merchants.py --count 60
python3 generate_customer_behavior.py
python3 generate_fraud_cases.py --count 40
python3 generate_policy_docs.py
```

No third-party dependencies — stdlib only, so this runs with a bare
`python3`.
