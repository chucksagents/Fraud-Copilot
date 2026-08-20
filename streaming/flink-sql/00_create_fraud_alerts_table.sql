-- Creates the `fraud-alerts` table (topic + registered schema) with an
-- explicit, hand-controlled schema. Run this ONE FIRST, before any of the
-- five rule files, and only after deleting any existing `fraud-alerts`
-- topic (Topics tab) and `fraud-alerts-value` subject (Schema Registry) if
-- they still exist from earlier attempts.
--
-- Why explicit DDL instead of letting Flink infer the schema:
-- 1. A hand-authored JSON Schema using plain `additionalProperties` (no
--    Confluent vendor extensions) gets mis-inferred as an empty ROW<>
--    instead of MAP<STRING, STRING> for `evidence`.
-- 2. Using CREATE TABLE ... AS SELECT (CTAS) from amount_anomaly.sql fixed
--    the MAP issue, but Flink then inferred `account_id`'s nullability
--    from `transactions.account_id`, which is NOT NULL there -- so the
--    sink rejected the NULL account_id that login-based rules
--    (multiple_failed_logins, new_or_unusual_device, impossible_travel)
--    legitimately need to write, since login events have no account_id.
--
-- Declaring the schema by hand sidesteps both problems: `evidence` is a
-- real MAP<STRING, STRING>, and `account_id` is nullable, matching what
-- every rule actually produces.
--
-- Note: `generated_at` is a STRING (`CAST($rowtime AS STRING)` in each
-- rule), which renders in whatever local time zone the *submitting Flink
-- session* happens to be using -- so sorting by it across rules can come
-- out wrong. Don't sort by it; use the table's own built-in `$rowtime`
-- metadata column instead (see README's "Don't sort by generated_at"
-- section). A real TIMESTAMP_LTZ column would fix this properly but
-- requires dropping and recreating this table, which isn't worth it here
-- since `$rowtime` already solves the sorting problem.

CREATE TABLE `fraud-alerts` (
  alert_id STRING NOT NULL,
  generated_at STRING NOT NULL,
  customer_id STRING NOT NULL,
  account_id STRING,
  rule_triggered STRING NOT NULL,
  severity STRING NOT NULL,
  related_event_ids ARRAY<STRING> NOT NULL,
  evidence MAP<STRING, STRING> NOT NULL,
  status STRING NOT NULL
) WITH (
  'value.format' = 'json-registry'
);
