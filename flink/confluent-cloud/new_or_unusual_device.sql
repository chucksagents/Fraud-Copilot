-- Rule: new_or_unusual_device
-- Flags the first time we see a given (customer_id, device_id) pair in the
-- login-events stream. Standard Flink "deduplication" pattern
-- (ROW_NUMBER() OVER ... WHERE rn = 1).
--
-- Caveat: state starts empty when this job starts, so a customer's own
-- existing devices will each look "new" once, the first time they show up
-- in the stream after the job is deployed. Acceptable for a demo; a
-- production version would seed state from data-gen's devices.json first.
--
-- Run this only after amount_anomaly.sql has created the `fraud-alerts`
-- table. The explicit column list below is required: Confluent Cloud
-- Flink tables always carry an implicit `key` BYTES bucket-key column
-- that this query doesn't produce, and without naming columns the
-- INSERT would fail on column-count mismatch.

INSERT INTO `fraud-alerts` (alert_id, generated_at, customer_id, account_id, rule_triggered, severity, related_event_ids, evidence, status)
SELECT
  UUID() AS alert_id,
  CAST(event_time AS STRING) AS generated_at,
  customer_id,
  CAST(NULL AS STRING) AS account_id,
  'new_or_unusual_device' AS rule_triggered,
  'low' AS severity,
  ARRAY[event_id] AS related_event_ids,
  MAP['device_id', device_id, 'auth_method', auth_method] AS evidence,
  'new' AS status
FROM (
  SELECT *, `$rowtime` AS event_time,
    ROW_NUMBER() OVER (
      PARTITION BY customer_id, device_id
      ORDER BY `$rowtime`
    ) AS rn
  FROM `login-events`
  WHERE success = TRUE
)
WHERE rn = 1;
