# Flink SQL

Deterministic fraud-signal rules, one statement per `.sql` file, each a
standing Flink Statement once submitted.

## Prerequisite: delete any existing `fraud-alerts` topic/schema, then run 00

We've hit two rounds of Flink mis-inferring the `fraud-alerts` schema:

1. A hand-authored JSON Schema using plain `additionalProperties` (no
   Confluent vendor extensions) got mis-inferred as an empty `ROW<>`
   instead of `MAP<STRING, STRING>` for `evidence`.
2. Recreating the table via `CREATE TABLE ... AS SELECT` from
   `amount_anomaly.sql` fixed the MAP issue, but Flink then inferred
   `account_id`'s nullability from `transactions.account_id` (NOT NULL
   there), so the sink rejected the NULL `account_id` that login-based
   rules legitimately need to write.

The fix: stop letting Flink infer the schema at all. `00_create_fraud_alerts_table.sql`
declares it by hand -- `evidence` as a real `MAP<STRING, STRING>`,
`account_id` nullable.

Before running anything:

1. Confluent Cloud console -> Topics -> delete `fraud-alerts` (if it exists).
2. Schema Registry -> delete the `fraud-alerts-value` subject (if it's still
   there after step 1).
3. Run `00_create_fraud_alerts_table.sql` in the Flink SQL workspace.

## Don't sort by `generated_at` -- use `$rowtime` instead

`generated_at` is a `STRING` built with `CAST($rowtime AS STRING)` (or
`CAST(window_end AS STRING)` for the windowed rules). That cast renders in
whatever local time zone the *submitting Flink session* happens to be
using, and since each rule is its own separately-submitted Statement, two
rules can stamp the same real-world instant with strings that differ by
hours. `ORDER BY generated_at DESC` across rules can come out wrong even
though each rule's own alerts look correctly ordered in isolation.

`fraud-alerts` is a Kafka-backed table like every other one here, so it
gets the same implicit `` `$rowtime` `` metadata column (the Kafka
broker's actual append timestamp, set by Kafka itself -- not by any Flink
session's local time zone). Use that to sort instead:

```sql
SELECT * FROM `fraud-alerts` ORDER BY `$rowtime` DESC LIMIT 20;
```

This needs no schema change and works against alerts already in the
topic. (A proper fix would make `generated_at` a real `TIMESTAMP_LTZ(3)`
column, but that requires dropping and recreating `fraud-alerts` --
skipped for now since `$rowtime` already solves the sorting problem.)

## Rules

- `00_create_fraud_alerts_table.sql` -- **run this first**, once. Creates
  the `fraud-alerts` table/topic/schema with an explicit, hand-controlled
  schema.
- `amount_anomaly.sql` -- a transaction > 5x the customer's own trailing average
- `high_velocity.sql` -- 4+ transactions on one card within 2 minutes
- `multiple_failed_logins.sql` -- 3+ failed logins for one customer within 3 minutes
- `new_or_unusual_device.sql` -- first-ever login from a given (customer, device) pair
- `impossible_travel.sql` -- two successful logins, different countries, within 20 minutes

All use Confluent's built-in `$rowtime` metadata column for event-time
windowing/ordering -- no manual watermark setup needed. Once `00_...` has
run, the five rules have no ordering dependency on each other.

Every rule uses an explicit column list on `INSERT INTO` (`INSERT INTO
`fraud-alerts` (alert_id, generated_at, ...)`) rather than a bare `INSERT
INTO `fraud-alerts``. This is required: Confluent Cloud Flink tables
always carry an implicit `key` BYTES bucket-key column, and without
naming columns the insert's 9 produced columns won't line up against the
table's 10.

## Testing order

Run these one at a time in the Flink SQL workspace, not all at once --
easier to debug if something doesn't parse.

1. `00_create_fraud_alerts_table.sql` (creates the table -- run once)
2. `amount_anomaly.sql`
3. `high_velocity.sql`
4. `multiple_failed_logins.sql`
5. `new_or_unusual_device.sql`
6. `impossible_travel.sql`

`amount_anomaly.sql` has a cold-start dependency: a customer's first
transaction has no prior average to compare against, so nothing fires
until customers have history. Send a baseline batch (e.g. 1000 normal
transactions, no anomalies) before submitting the statement, then send an
anomaly batch (e.g. 200 transactions, 50% anomaly rate) afterward.

After submitting a statement, send a fresh batch of events through the
producers (`streaming/producers/`, `--sink kafka`, with `--anomaly-rate` /
`--burst-rate` etc. turned up) and check `fraud-alerts` for output:

```sql
SELECT * FROM `fraud-alerts` ORDER BY `$rowtime` DESC LIMIT 20;
```

Each submitted statement becomes a continuously-running Statement that
keeps consuming CFUs until stopped -- check the Statements list and stop
ones you're not actively using, same cost consideration as the Flink
compute pool itself.

## Known simplifications (documented in each file's comments)

- `new_or_unusual_device` and `amount_anomaly` don't join against
  `data-gen/fixtures/` reference data (not wired into Kafka) -- both are
  self-contained to the live stream and have a cold-start caveat.
- `multiple_failed_logins` doesn't replicate the full severity nuance from
  `data-gen/fixtures/policies/policy_multiple_failed_logins.md` (e.g.
  correlating with an eventual success from a new device) -- that
  correlation is left to the investigation agent downstream.
