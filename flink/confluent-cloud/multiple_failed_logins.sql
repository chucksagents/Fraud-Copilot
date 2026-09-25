-- Rule: multiple_failed_logins
-- Flags a customer with 3+ failed logins inside a rolling 3-minute window.
-- Simplification: only counts failures. Correlating with an eventual
-- success from a new device (the extra nuance in the policy doc) is left
-- to the investigation agent downstream, not duplicated here.
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
  CAST(NULL AS STRING) AS account_id,  -- login events have no account_id
  'multiple_failed_logins' AS rule_triggered,
  CASE WHEN fail_count >= 5 THEN 'high' ELSE 'medium' END AS severity,
  event_ids AS related_event_ids,
  MAP['failed_count', CAST(fail_count AS STRING), 'window_seconds', '180'] AS evidence,
  'new' AS status
FROM (
  SELECT
    window_start,
    window_end,
    customer_id,
    COUNT(*) AS fail_count,
    ARRAY_AGG(event_id) AS event_ids
  FROM TABLE(
    TUMBLE(TABLE `login-events`, DESCRIPTOR(`$rowtime`), INTERVAL '3' MINUTES)
  )
  WHERE success = FALSE
  GROUP BY window_start, window_end, customer_id
)
WHERE fail_count >= 3;
