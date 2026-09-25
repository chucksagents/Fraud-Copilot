-- Rule: multiple_failed_logins -- password guessing / credential stuffing.
-- Fires on the 3rd failed login for one customer within any rolling
-- 3 minutes.
--
-- Deliberately narrow: it fires early and does not wait to see what happens
-- next. Whether the burst ended in a success from an unknown device (much
-- worse) is exactly the kind of follow-up the investigation agent checks by
-- reading the customer's recent activity. The rule decides "look at this";
-- the investigation decides what it means.

INSERT INTO fraud_alerts
SELECT
  MD5(CONCAT('multiple_failed_logins:', event_id))                     AS alert_id,
  DATE_FORMAT(event_time, 'yyyy-MM-dd''T''HH:mm:ss.SSS''Z''')           AS generated_at,
  customer_id,
  CAST(NULL AS STRING)                                                  AS account_id,
  'multiple_failed_logins'                                              AS rule_triggered,
  'medium'                                                              AS severity,
  event_ids                                                             AS related_event_ids,
  MAP[
    'failed_count',        CAST(fail_count AS STRING),
    'window_seconds',      '180',
    'device_id',           device_id,
    'login_city',          location.city,
    'login_country',       location.country,
    'last_failure_reason', COALESCE(failure_reason, 'unknown')
  ]                                                                     AS evidence,
  'new'                                                                 AS status
FROM (
  SELECT
    event_id, event_time, customer_id, device_id, location, failure_reason,
    COUNT(*)            OVER w AS fail_count,
    ARRAY_AGG(event_id) OVER w AS event_ids
  FROM login_events
  WHERE success = FALSE
  WINDOW w AS (
    PARTITION BY customer_id
    ORDER BY event_time
    RANGE BETWEEN INTERVAL '3' MINUTE PRECEDING AND CURRENT ROW
  )
)
WHERE fail_count = 3;
