"""
Shared utilities for producers: env loading, schema validation, and a
pluggable output sink (kafka / stdout / file).

Kafka support (confluent_kafka) is imported lazily so `--sink stdout` and
`--sink file` work without confluent-kafka (and its librdkafka build deps)
installed — useful before Confluent Cloud credentials exist.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "docs" / "schemas"
FIXTURES_DIR = REPO_ROOT / "data-gen" / "fixtures"
ENV_FILE = REPO_ROOT / "infra" / ".env"

try:
    from dotenv import load_dotenv
except ImportError:
    print(
        "[common] python-dotenv is not installed — infra/.env will NOT be loaded "
        "(only real environment variables will be used). Run "
        "`pip install -r streaming/producers/requirements.txt`.",
        file=sys.stderr,
    )
else:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        print(
            f"[common] {ENV_FILE} not found — copy infra/.env.example to infra/.env "
            "and fill in your Kafka credentials.",
            file=sys.stderr,
        )


def load_schema(name: str) -> dict:
    with open(SCHEMAS_DIR / name) as f:
        return json.load(f)


def validate_event(event: dict, schema: dict) -> None:
    """Raises jsonschema.ValidationError if the event does not conform."""
    jsonschema.validate(instance=event, schema=schema)


def load_fixture(name: str) -> Any:
    path = FIXTURES_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python3 data-gen/generators/generate_all.py` first."
        )
    with open(path) as f:
        return json.load(f)


class Sink:
    """Pluggable output for a stream of events: kafka topic, stdout, or a
    local .jsonl file. Producers should not care which mode is active."""

    def __init__(self, mode: str, topic: str, file_path: Optional[Path] = None):
        if mode not in ("kafka", "stdout", "file"):
            raise ValueError(f"unknown sink mode: {mode}")
        self.mode = mode
        self.topic = topic
        self._producer = None
        self._file = None
        self.sent_count = 0

        if mode == "kafka":
            from confluent_kafka import Producer  # deferred import, see module docstring

            bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
            security_protocol = os.environ.get("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")

            if not bootstrap_servers:
                raise RuntimeError(
                    "KAFKA_BOOTSTRAP_SERVERS is not set. Check that infra/.env exists, "
                    "has KAFKA_BOOTSTRAP_SERVERS filled in, and that python-dotenv is "
                    "installed (pip install -r streaming/producers/requirements.txt) — "
                    "see the [common] warning above if it printed one."
                )

            conf = {"bootstrap.servers": bootstrap_servers}

            if security_protocol != "PLAINTEXT":
                sasl_username = os.environ.get("KAFKA_API_KEY", "")
                sasl_password = os.environ.get("KAFKA_API_SECRET", "")
                if not sasl_username or not sasl_password:
                    raise RuntimeError(
                        "KAFKA_SECURITY_PROTOCOL is "
                        f"{security_protocol!r} but KAFKA_API_KEY / KAFKA_API_SECRET "
                        "are missing. This almost always means infra/.env wasn't loaded "
                        "— check that infra/.env exists (not just infra/.env.example), "
                        "that KAFKA_API_KEY and KAFKA_API_SECRET are filled in on their "
                        "own lines, and that python-dotenv is installed: "
                        "pip install -r streaming/producers/requirements.txt"
                    )
                conf.update(
                    {
                        "security.protocol": security_protocol,
                        "sasl.mechanisms": "PLAIN",
                        "sasl.username": sasl_username,
                        "sasl.password": sasl_password,
                    }
                )
            self._producer = Producer(conf)
        elif mode == "file":
            file_path = file_path or (FIXTURES_DIR / f"{topic}.jsonl")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(file_path, "a")

    def send(self, event: dict, key: Optional[str] = None) -> None:
        line = json.dumps(event, default=str)
        if self.mode == "kafka":
            self._producer.produce(self.topic, key=key or "", value=line)
            self._producer.poll(0)
        elif self.mode == "file":
            self._file.write(line + "\n")
        else:  # stdout
            print(line)
        self.sent_count += 1

    def flush(self) -> None:
        if self._producer is not None:
            self._producer.flush()
        if self._file is not None:
            self._file.flush()
            self._file.close()
