-- Rule: new_or_unusual_device
-- Fires the first time a customer successfully logs in from a device that is
-- not in their trusted-device list (from the customer_profiles reference
-- table).
--
-- Two patterns combined:
--   1. Deduplication: ROW_NUMBER() ... WHERE rn = 1 keeps only the first
--      successful login per (customer, device), so a new device alerts once,
--      not on every login. Ordered by proc_time: "first seen by us".
--   2. Enrichment: a regular join against reference data to ask "is this
--      device one we know?". Without it, every customer's existing devices
--      would look new the moment the job starts.
--
-- Severity: medium if the login also comes from outside the customer's home
-- country, otherwise low (a new phone at home is usually just a new phone).

INSERT INTO fraud_alerts
SELECT /*+ STATE_TTL('l' = '30 min', 'p' = '3650 d') */
  MD5(CONCAT('new_or_unusual_device:', l.event_id))                    AS alert_id,
  DATE_FORMAT(l.event_time, 'yyyy-MM-dd''T''HH:mm:ss.SSS''Z''')         AS generated_at,
  l.customer_id,
  CAST(NULL AS STRING)                                                  AS account_id,
  'new_or_unusual_device'                                               AS rule_triggered,
  CASE WHEN l.location.country <> p.home_country THEN 'medium' ELSE 'low' END AS severity,
  ARRAY[l.event_id]                                                     AS related_event_ids,
  MAP[
    'device_id',            l.device_id,
    'auth_method',          l.auth_method,
    'login_city',           l.location.city,
    'login_country',        l.location.country,
    'home_country',         p.home_country,
    'trusted_device_count', CAST(CARDINALITY(p.trusted_device_ids) AS STRING)
  ]                                                                     AS evidence,
  'new'                                                                 AS status
FROM (
  SELECT * FROM (
    SELECT *,
      ROW_NUMBER() OVER (PARTITION BY customer_id, device_id ORDER BY proc_time) AS rn
    FROM login_events
    WHERE success = TRUE
  )
  WHERE rn = 1
) AS l
JOIN customer_profiles AS p
  ON l.customer_id = p.customer_id
WHERE NOT ARRAY_CONTAINS(p.trusted_device_ids, l.device_id);
