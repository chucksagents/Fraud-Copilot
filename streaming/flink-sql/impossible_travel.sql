-- Rule: impossible_travel
-- Flags two successful logins by the same customer, from different
-- countries, within a 20-minute window. An interval self-join: b must
-- happen strictly after a, within the window, so each real pair fires
-- exactly once (not mirrored).
--
-- Run this only after amount_anomaly.sql has created the `fraud-alerts`
-- table. The explicit column list below is required: Confluent Cloud
-- Flink tables always carry an implicit `key` BYTES bucket-key column
-- that this query doesn't produce, and without naming columns the
-- INSERT would fail on column-count mismatch.

INSERT INTO `fraud-alerts` (alert_id, generated_at, customer_id, account_id, rule_triggered, severity, related_event_ids, evidence, status)
SELECT
  UUID() AS alert_id,
  CAST(b.`$rowtime` AS STRING) AS generated_at,
  a.customer_id AS customer_id,
  CAST(NULL AS STRING) AS account_id,
  'impossible_travel' AS rule_triggered,
  'high' AS severity,
  ARRAY[a.event_id, b.event_id] AS related_event_ids,
  MAP[
    'first_country', a.location.country,
    'second_country', b.location.country,
    'minutes_apart', CAST(TIMESTAMPDIFF(MINUTE, a.`$rowtime`, b.`$rowtime`) AS STRING)
  ] AS evidence,
  'new' AS status
FROM `login-events` a
JOIN `login-events` b
  ON a.customer_id = b.customer_id
  AND a.event_id <> b.event_id
  AND b.`$rowtime` BETWEEN a.`$rowtime` + INTERVAL '1' SECOND
                        AND a.`$rowtime` + INTERVAL '20' MINUTE
WHERE a.success = TRUE
  AND b.success = TRUE
  AND a.location.country <> b.location.country;
