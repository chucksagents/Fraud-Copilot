-- Rule: amount_anomaly
-- Fires when a transaction is more than 5x the customer's average amount.
--
-- Enrichment pattern: join each transaction with the customer's profile
-- (reference data published to Kafka). This replaces the earlier
-- stream-only version, which computed a running average and could not fire
-- until a customer had history (the "cold start" problem).
--
-- STATE_TTL: a regular join keeps both sides in state. Transactions only
-- need to wait briefly for a matching profile; profiles must be kept.
--
-- Severity: high above 10x, or when the merchant category is not one the
-- customer normally uses; otherwise medium.

INSERT INTO fraud_alerts
SELECT /*+ STATE_TTL('t' = '10 min', 'p' = '3650 d') */
  MD5(CONCAT('amount_anomaly:', t.event_id))                           AS alert_id,
  DATE_FORMAT(t.event_time, 'yyyy-MM-dd''T''HH:mm:ss.SSS''Z''')         AS generated_at,
  t.customer_id,
  t.account_id,
  'amount_anomaly'                                                      AS rule_triggered,
  CASE
    WHEN t.amount > 10 * p.avg_transaction_amount THEN 'high'
    WHEN NOT ARRAY_CONTAINS(p.typical_merchant_categories, t.merchant_category) THEN 'high'
    ELSE 'medium'
  END                                                                   AS severity,
  ARRAY[t.event_id]                                                     AS related_event_ids,
  MAP[
    'amount',               CAST(t.amount AS STRING),
    'customer_avg_amount',  CAST(p.avg_transaction_amount AS STRING),
    'multiple',             CAST(ROUND(t.amount / p.avg_transaction_amount, 1) AS STRING),
    'merchant_id',          t.merchant_id,
    'merchant_category',    t.merchant_category,
    'familiar_category',    CASE WHEN ARRAY_CONTAINS(p.typical_merchant_categories, t.merchant_category)
                                 THEN 'true' ELSE 'false' END,
    'channel',              t.channel,
    'transaction_city',     t.location.city,
    'transaction_country',  t.location.country
  ]                                                                     AS evidence,
  'new'                                                                 AS status
FROM transactions AS t
JOIN customer_profiles AS p
  ON t.customer_id = p.customer_id
WHERE t.amount > 5 * p.avg_transaction_amount;
