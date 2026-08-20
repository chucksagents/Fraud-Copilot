"""
Thin wrapper for publishing to `case-actions`. Plain JSON, no schema-registry
wire format -- unlike fraud-alerts, no Flink table currently reads this
topic, so there's nothing to conform to yet (see streaming/flink-sql/). If a
Flink table gets created for it later with 'value.format' = 'json-registry',
switch publish_case_action() to use
confluent_kafka.schema_registry.json_schema.JSONSerializer instead of a bare
json.dumps().
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from confluent_kafka import Producer

from . import config

logger = logging.getLogger("alert_api.kafka_producer")

_producer: Optional[Producer] = None


def get_producer() -> Producer:
    global _producer
    if _producer is None:
        _producer = Producer(config.kafka_conf())
    return _producer


def publish_case_action(action: dict) -> None:
    producer = get_producer()
    producer.produce(
        config.TOPIC_CASE_ACTIONS,
        key=action["case_id"],
        value=json.dumps(action, default=str),
    )
    # Synchronous flush keeps this simple and correct for demo throughput --
    # a production version would poll/batch instead of flushing per request.
    producer.flush(timeout=5)
