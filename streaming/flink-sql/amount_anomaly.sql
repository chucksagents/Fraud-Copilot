-- Rule: amount_anomaly
-- Flags a transaction that's more than 5x a customer's own trailing
-- average transaction amount, computed purely from the stream itself (not
-- from data-gen's customer_behavior.json baseline -- no external
-- reference-data join is wired up yet). A customer's very first
-- transaction has no prior average and is correctly never flagged.
--
-- Caveat: per-customer state for the trailing average grows unboundedly.
-- Fine at demo scale; a production version should bound it with a
-- trailing window (e.g. last 90 days) instead of UNBOUNDED PRECEDING.
--
-- Note on the OVER window: Flink's streaming OVER aggregates only support
-- frames that end at CURRENT ROW ("ROWS BETWEEN UNBOUNDED PRECEDING AND
-- CURRENT ROW"). A frame like "... AND 1 PRECEDING" (excluding the
-- current row) isn't supported and fails to submit with a confusing
-- "OVER RANGE FOLLOWING windows are not supported yet" error. So instead
-- we compute the running sum/count INCLUDING the current row (the
-- supported frame), then subtract the current row's own amount/count to
-- get the prior (exclusive-of-self) average.
--
-- Run this only after 00_create_fraud_alerts_table.sql has created the
-- `fraud-alerts` table. The explicit column list below is required:
-- Confluent Cloud Flink tables always carry an implicit `key` BYTES
-- bucket-key column that this query doesn't produce, and without naming
-- columns the INSERT would fail on column-count mismatch.

INSERT INTO `fraud-alerts` (alert_id, generated_at, customer_id, account_id, rule_triggered, severity, related_event_ids, evidence, status)
SELECT
  UUID() AS alert_id,
  CAST(event_time AS STRING) AS generated_at,
  customer_id,
  account_id,
  'amount_anomaly' AS rule_triggered,
  CASE WHEN amount > 10 * trailing_avg_amount THEN 'high' ELSE 'medium' END AS severity,
  ARRAY[event_id] AS related_event_ids,
  MAP[
    'amount', CAST(amount AS STRING),
    'trailing_avg_amount', CAST(trailing_avg_amount AS STRING),
    'multiple', CAST(amount / trailing_avg_amount AS STRING)
  ] AS evidence,
  'new' AS status
FROM (
  SELECT *,
    CASE
      WHEN running_count = 1 THEN CAST(NULL AS DOUBLE)
      ELSE (running_sum - amount) / (running_count - 1)
    END AS trailing_avg_amount
  FROM (
    SELECT *, `$rowtime` AS event_time,
      SUM(amount) OVER (
        PARTITION BY customer_id
        ORDER BY `$rowtime`
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      ) AS running_sum,
      COUNT(*) OVER (
        PARTITION BY customer_id
        ORDER BY `$rowtime`
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      ) AS running_count
    FROM `transactions`
  )
)
WHERE trailing_avg_amount IS NOT NULL
  AND amount > 5 * trailing_avg_amount;
