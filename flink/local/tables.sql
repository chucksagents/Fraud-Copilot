-- Table definitions for the local Docker Compose stack.
--
-- The rule files in ../rules/ only reference the tables and columns declared
-- here: transactions, login_events, customer_profiles, fraud_alerts, plus the
-- computed columns event_time (event time, with a watermark) and proc_time.
-- That contract is what lets the same rule SQL run locally, in the test
-- harness (tests/flink/), and -- with a different version of this file --
-- on Confluent Cloud.

SET 'table.local-time-zone' = 'UTC';
SET 'parallelism.default' = '1';

-- Card transactions. Event time comes from the payload's `timestamp`, not
-- from when Kafka received the record: that is what makes replays and late
-- data behave predictably (see docs/decisions.md, "Event time").
CREATE TABLE IF NOT EXISTS transactions (
  event_id          STRING,
  event_type        STRING,
  `timestamp`       TIMESTAMP_LTZ(3),
  customer_id       STRING,
  account_id        STRING,
  card_id           STRING,
  amount            DOUBLE,
  currency          STRING,
  merchant_id       STRING,
  merchant_category STRING,
  channel           STRING,
  device_id         STRING,
  location          ROW<city STRING, country STRING, lat DOUBLE, lon DOUBLE>,
  event_time AS `timestamp`,
  proc_time  AS PROCTIME(),
  -- Tolerate events arriving up to 2 seconds out of order.
  WATERMARK FOR event_time AS event_time - INTERVAL '2' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'transactions',
  'properties.bootstrap.servers' = 'kafka:29092',
  'properties.group.id' = 'flink-fraud-rules',
  'scan.startup.mode' = 'earliest-offset',
  'format' = 'json',
  'json.timestamp-format.standard' = 'ISO-8601',
  'json.ignore-parse-errors' = 'true'
);

CREATE TABLE IF NOT EXISTS login_events (
  event_id       STRING,
  event_type     STRING,
  `timestamp`    TIMESTAMP_LTZ(3),
  customer_id    STRING,
  device_id      STRING,
  ip_address     STRING,
  location       ROW<city STRING, country STRING>,
  auth_method    STRING,
  success        BOOLEAN,
  failure_reason STRING,
  event_time AS `timestamp`,
  proc_time  AS PROCTIME(),
  WATERMARK FOR event_time AS event_time - INTERVAL '2' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'login-events',
  'properties.bootstrap.servers' = 'kafka:29092',
  'properties.group.id' = 'flink-fraud-rules',
  'scan.startup.mode' = 'earliest-offset',
  'format' = 'json',
  'json.timestamp-format.standard' = 'ISO-8601',
  'json.ignore-parse-errors' = 'true'
);

-- Reference data: each customer's normal behavior and trusted devices,
-- published once by `python -m datagen load-reference`. Rules join
-- against it to enrich events (see amount_anomaly.sql).
CREATE TABLE IF NOT EXISTS customer_profiles (
  customer_id                 STRING,
  home_city                   STRING,
  home_country                STRING,
  avg_transaction_amount      DOUBLE,
  stddev_transaction_amount   DOUBLE,
  typical_merchant_categories ARRAY<STRING>,
  typical_channels            ARRAY<STRING>,
  typical_countries           ARRAY<STRING>,
  trusted_device_ids          ARRAY<STRING>,
  avg_daily_transaction_count DOUBLE
) WITH (
  'connector' = 'kafka',
  'topic' = 'customer-profiles',
  'properties.bootstrap.servers' = 'kafka:29092',
  'properties.group.id' = 'flink-fraud-rules',
  'scan.startup.mode' = 'earliest-offset',
  'format' = 'json',
  'json.ignore-parse-errors' = 'true'
);

-- Output: one row per alert, consumed by the fraud API.
CREATE TABLE IF NOT EXISTS fraud_alerts (
  alert_id          STRING,
  generated_at      STRING,
  customer_id       STRING,
  account_id        STRING,
  rule_triggered    STRING,
  severity          STRING,
  related_event_ids ARRAY<STRING>,
  evidence          MAP<STRING, STRING>,
  status            STRING
) WITH (
  'connector' = 'kafka',
  'topic' = 'fraud-alerts',
  'properties.bootstrap.servers' = 'kafka:29092',
  'format' = 'json'
);
