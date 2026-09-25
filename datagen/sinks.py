"""
Where generated events go: a Kafka topic, stdout, JSON-lines files, or an
in-memory list (tests). Producers don't care which one is active.

Kafka settings come from environment variables (loaded from the repo-root
`.env` if python-dotenv is installed). Defaults target the local Docker
Compose stack, so nothing needs configuring for the lab.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"

try:
    from dotenv import load_dotenv
except ImportError:  # optional; plain env vars still work
    pass
else:
    load_dotenv(REPO_ROOT / ".env")

TOPICS = {
    "transactions": os.environ.get("TOPIC_TRANSACTIONS", "transactions"),
    "login-events": os.environ.get("TOPIC_LOGIN_EVENTS", "login-events"),
    "customer-profiles": os.environ.get("TOPIC_CUSTOMER_PROFILES", "customer-profiles"),
}

_SCHEMA_FOR_TOPIC = {
    "transactions": "transaction.schema.json",
    "login-events": "login-event.schema.json",
}


def kafka_conf() -> dict[str, Any]:
    """confluent-kafka client config. PLAINTEXT for the local stack; set
    KAFKA_SECURITY_PROTOCOL=SASL_SSL plus an API key/secret for Confluent Cloud."""
    conf: dict[str, Any] = {
        "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    }
    protocol = os.environ.get("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
    if protocol != "PLAINTEXT":
        key, secret = os.environ.get("KAFKA_API_KEY"), os.environ.get("KAFKA_API_SECRET")
        if not key or not secret:
            raise SystemExit(
                f"KAFKA_SECURITY_PROTOCOL={protocol} needs KAFKA_API_KEY and KAFKA_API_SECRET "
                "(set them in .env). See lab/extensions/confluent-cloud.md.")
        conf.update({"security.protocol": protocol, "sasl.mechanisms": "PLAIN",
                     "sasl.username": key, "sasl.password": secret})
    return conf


class Validator:
    """Validates events against schemas/ before they leave the process, so a
    malformed event fails loudly here instead of silently in Flink."""

    def __init__(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self._validators = None
            return
        self._validators = {}
        for topic, name in _SCHEMA_FOR_TOPIC.items():
            schema = json.loads((SCHEMAS_DIR / name).read_text())
            self._validators[topic] = jsonschema.Draft7Validator(schema)

    def check(self, topic: str, event: dict) -> None:
        if self._validators and topic in self._validators:
            self._validators[topic].validate(event)


class Sink:
    def __init__(self, mode: str, out_dir: Optional[Path] = None):
        if mode not in ("kafka", "stdout", "file", "memory"):
            raise ValueError(f"unknown sink: {mode}")
        self.mode = mode
        self.count = 0
        self.records: list[tuple[str, dict]] = []
        self._validator = Validator()
        self._files: dict[str, Any] = {}
        self._out_dir = out_dir
        self._producer = None
        if mode == "kafka":
            try:
                from confluent_kafka import Producer
            except ImportError:
                raise SystemExit("confluent-kafka is not installed: pip install -r requirements.txt")
            self._producer = Producer(kafka_conf())

    def send(self, topic: str, event: dict, key: Optional[str] = None) -> None:
        self._validator.check(topic, event)
        line = json.dumps(event)
        if self.mode == "kafka":
            self._producer.produce(TOPICS.get(topic, topic), key=key or "", value=line)
            self._producer.poll(0)
        elif self.mode == "file":
            if topic not in self._files:
                self._out_dir.mkdir(parents=True, exist_ok=True)
                self._files[topic] = open(self._out_dir / f"{topic}.jsonl", "a")
            self._files[topic].write(line + "\n")
        elif self.mode == "memory":
            self.records.append((topic, event))
        else:
            print(f"{topic:>13}  {line}")
        self.count += 1

    def deliver(self) -> None:
        """Push buffered Kafka messages out now (no-op for other sinks)."""
        if self._producer is not None:
            self._producer.flush(5)

    def flush(self) -> None:
        if self._producer is not None:
            remaining = self._producer.flush(10)
            if remaining:
                raise SystemExit(f"{remaining} events were not delivered -- is Kafka up? (make up)")
        for f in self._files.values():
            f.close()
        self._files.clear()
