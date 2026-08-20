-- Rule: high_velocity
-- Flags a card with 4+ transactions inside a rolling 2-minute tumbling
-- window. Uses Confluent's built-in `$rowtime` (Kafka record time) --
-- no manual watermark setup needed, every Kafka-backed table has one.
--
-- Run this only after amount_anomaly.sql has created the `fraud-alerts`
-- table. The explicit column list below is required: Confluent Cloud
-- Flink tables always carry an implicit `key` BYTES bucket-key column
-- that this query doesn't produce, and without naming columns the
-- INSERT would fail on column-count mismatch.

INSERT INTO `fraud-alerts` (alert_id, generated_at, customer_id, account_id, rule_triggered, severity, related_event_ids, evidence, status)
SELECT
  UUID() AS alert_id,
  CAST(window_end AS STRING) AS generated_at,
  customer_id,
  account_id,
  'high_velocity' AS rule_triggered,
  CASE WHEN txn_count >= 6 THEN 'high' ELSE 'medium' END AS severity,
  event_ids AS related_event_ids,
  MAP['transaction_count', CAST(txn_count AS STRING), 'window_seconds', '120'] AS evidence,
  'new' AS status
FROM (
  SELECT
    window_start,
    window_end,
    card_id,
    -- customer_id/account_id are 1:1 with card_id in our data; MAX() just
    -- picks the (only) value out of each group
    MAX(customer_id) AS customer_id,
    MAX(account_id) AS account_id,
    COUNT(*) AS txn_count,
    ARRAY_AGG(event_id) AS event_ids
  FROM TABLE(
    TUMBLE(TABLE `transactions`, DESCRIPTOR(`$rowtime`), INTERVAL '2' MINUTES)
  )
  GROUP BY window_start, window_end, card_id
)
WHERE txn_count >= 4;
