-- Rule: high_velocity -- card testing.
-- Fires on the 4th transaction on one card within any rolling 2 minutes.
--
-- Why an OVER window and not TUMBLE: a tumbling window only emits when it
-- closes, and a burst that straddles a window boundary gets split in two
-- and may never reach the threshold. A RANGE OVER window slides with each
-- event, so the alert fires at the 4th swipe -- which is also when a fraud
-- team wants to know. `= 4` (not `>= 4`) makes one burst produce one alert.
--
-- Severity: tiny amounts are the card-testing signature (fraudsters
-- checking a stolen card number works before using it), so a burst whose
-- largest charge is <= $15 is high; anything else is medium.

INSERT INTO fraud_alerts
SELECT
  MD5(CONCAT('high_velocity:', event_id))                              AS alert_id,
  DATE_FORMAT(event_time, 'yyyy-MM-dd''T''HH:mm:ss.SSS''Z''')           AS generated_at,
  customer_id,
  account_id,
  'high_velocity'                                                       AS rule_triggered,
  CASE WHEN max_amount <= 15 THEN 'high' ELSE 'medium' END              AS severity,
  event_ids                                                             AS related_event_ids,
  MAP[
    'card_id',           card_id,
    'transaction_count', CAST(txn_count AS STRING),
    'window_seconds',    '120',
    'total_amount',      CAST(ROUND(total_amount, 2) AS STRING),
    'max_amount',        CAST(max_amount AS STRING)
  ]                                                                     AS evidence,
  'new'                                                                 AS status
FROM (
  SELECT
    event_id, event_time, customer_id, account_id, card_id,
    COUNT(*)            OVER w AS txn_count,
    SUM(amount)         OVER w AS total_amount,
    MAX(amount)         OVER w AS max_amount,
    ARRAY_AGG(event_id) OVER w AS event_ids
  FROM transactions
  WINDOW w AS (
    PARTITION BY card_id
    ORDER BY event_time
    RANGE BETWEEN INTERVAL '2' MINUTE PRECEDING AND CURRENT ROW
  )
)
WHERE txn_count = 4;
