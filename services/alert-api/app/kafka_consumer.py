"""
Background Kafka consumer: reads `fraud-alerts` (written by Flink with
'value.format' = 'json-registry') and persists each alert, auto-opening a
Case for it the moment it lands.

`json-registry` messages are schema-registry-framed: each value is

    [1 magic byte 0x00][4-byte big-endian schema id][JSON payload bytes]

per Confluent's wire format (true whether the underlying format is Avro,
Protobuf, or JSON Schema). We only need to read the payload, not validate
against the registered schema, so we just skip the 5-byte header rather than
pulling in a SchemaRegistryClient + JSONDeserializer for this. If that ever
proves too fragile, swap _decode_json_registry() for
confluent_kafka.schema_registry.json_schema.JSONDeserializer.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid

from confluent_kafka import Consumer

from . import config
from .db import SessionLocal
from .models import Alert, Case

logger = logging.getLogger("alert_api.kafka_consumer")

CONFLUENT_WIRE_FORMAT_HEADER_LEN = 5  # 1 magic byte + 4-byte schema id


def _decode_json_registry(raw: bytes) -> dict:
    if len(raw) > CONFLUENT_WIRE_FORMAT_HEADER_LEN and raw[0] == 0x00:
        raw = raw[CONFLUENT_WIRE_FORMAT_HEADER_LEN:]
    return json.loads(raw)


def _upsert_alert(db, payload: dict) -> None:
    alert_id = payload["alert_id"]
    if db.get(Alert, alert_id) is not None:
        return  # alerts are immutable once ingested -- nothing to update

    alert = Alert(
        alert_id=alert_id,
        generated_at=payload["generated_at"],
        customer_id=payload["customer_id"],
        account_id=payload.get("account_id"),
        rule_triggered=payload["rule_triggered"],
        severity=payload["severity"],
        related_event_ids=payload.get("related_event_ids", []),
        evidence=payload.get("evidence", {}),
        status=payload.get("status", "new"),
    )
    db.add(alert)
    db.add(Case(case_id=str(uuid.uuid4()), alert_id=alert_id))
    db.commit()
    logger.info("ingested alert %s (rule=%s)", alert_id, payload["rule_triggered"])


def _consume_loop(stop_event: threading.Event) -> None:
    conf = config.kafka_conf(group_id=config.CONSUMER_GROUP_ID)
    # earliest: on a brand-new consumer group, pick up every alert already
    # sitting in the topic (including ones from before this service existed),
    # not just ones produced after it starts. Once a group has committed
    # offsets, restarts resume from there as normal -- this only affects the
    # very first run of a given group.id.
    conf["auto.offset.reset"] = "earliest"
    conf["enable.auto.commit"] = True

    consumer = Consumer(conf)
    consumer.subscribe([config.TOPIC_FRAUD_ALERTS])
    logger.info(
        "subscribed to %s (group=%s)", config.TOPIC_FRAUD_ALERTS, config.CONSUMER_GROUP_ID
    )

    try:
        while not stop_event.is_set():
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.warning("consumer error: %s", msg.error())
                continue

            try:
                payload = _decode_json_registry(msg.value())
            except Exception:
                logger.exception("failed to decode a fraud-alerts message, skipping it")
                continue

            db = SessionLocal()
            try:
                _upsert_alert(db, payload)
            except Exception:
                db.rollback()
                logger.exception(
                    "failed to persist alert %s, skipping it", payload.get("alert_id")
                )
            finally:
                db.close()
    finally:
        consumer.close()


def start(stop_event: threading.Event) -> threading.Thread:
    thread = threading.Thread(
        target=_consume_loop, args=(stop_event,), daemon=True, name="fraud-alerts-consumer"
    )
    thread.start()
    return thread
