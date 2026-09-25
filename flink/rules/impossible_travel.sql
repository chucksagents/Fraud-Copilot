-- Rule: impossible_travel
-- Fires when one customer has two successful logins from different
-- countries within 20 minutes.
--
-- An interval join of login_events with itself: for each login a, find a
-- later login b by the same customer within the time bound. Because b must
-- be strictly after a, each pair fires once rather than twice (a,b and b,a).
-- Interval joins are event-time operators: Flink keeps each login in state
-- only until the watermark passes a.event_time + 20 minutes.
--
-- The rule cannot know about travel notices or corporate VPNs. That is on
-- purpose -- see the travel_vpn scenario.

INSERT INTO fraud_alerts
SELECT
  MD5(CONCAT('impossible_travel:', a.event_id, ':', b.event_id))      AS alert_id,
  DATE_FORMAT(b.event_time, 'yyyy-MM-dd''T''HH:mm:ss.SSS''Z''')         AS generated_at,
  a.customer_id,
  CAST(NULL AS STRING)                                                  AS account_id,
  'impossible_travel'                                                   AS rule_triggered,
  'high'                                                                AS severity,
  ARRAY[a.event_id, b.event_id]                                         AS related_event_ids,
  MAP[
    'first_city',     a.location.city,
    'first_country',  a.location.country,
    'first_device',   a.device_id,
    'second_city',    b.location.city,
    'second_country', b.location.country,
    'second_device',  b.device_id,
    'seconds_apart',  CAST(TIMESTAMPDIFF(SECOND, a.event_time, b.event_time) AS STRING)
  ]                                                                     AS evidence,
  'new'                                                                 AS status
FROM login_events AS a
JOIN login_events AS b
  ON  a.customer_id = b.customer_id
  AND b.event_time >  a.event_time
  AND b.event_time <= a.event_time + INTERVAL '20' MINUTE
WHERE a.success = TRUE
  AND b.success = TRUE
  AND a.location.country <> b.location.country;
