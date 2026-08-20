"""
Shared configuration for the alert/case API: env loading (mirrors
streaming/producers/common.py's convention) and Kafka connection settings.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = REPO_ROOT / "docs" / "schemas"
ENV_FILE = REPO_ROOT / "infra" / ".env"

try:
    from dotenv import load_dotenv
except ImportError:
    print(
        "[config] python-dotenv is not installed -- infra/.env will NOT be "
        "loaded (only real environment variables will be used). Run "
        "`pip install -r services/alert-api/requirements.txt`.",
        file=sys.stderr,
    )
else:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        print(
            f"[config] {ENV_FILE} not found -- copy infra/.env.example to "
            "infra/.env and fill in your Kafka credentials.",
            file=sys.stderr,
        )


TOPIC_FRAUD_ALERTS = os.environ.get("TOPIC_FRAUD_ALERTS", "fraud-alerts")
TOPIC_CASE_ACTIONS = os.environ.get("TOPIC_CASE_ACTIONS", "case-actions")
CONSUMER_GROUP_ID = os.environ.get("ALERT_API_CONSUMER_GROUP", "alert-api")
DB_URL = os.environ.get("ALERT_API_DB_URL", "sqlite:///./alerts.db")


def kafka_conf(group_id: Optional[str] = None) -> dict:
    """Build a confluent_kafka conf dict from env vars -- same convention as
    streaming/producers/common.py's Sink class, so it works against Confluent
    Cloud (SASL_SSL) or a local docker-compose Kafka (PLAINTEXT) unchanged."""
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
    security_protocol = os.environ.get("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")

    if not bootstrap_servers:
        raise RuntimeError(
            "KAFKA_BOOTSTRAP_SERVERS is not set. Check that infra/.env exists "
            "and has it filled in (see the [config] warning above if it printed one)."
        )

    conf = {"bootstrap.servers": bootstrap_servers}
    if group_id:
        conf["group.id"] = group_id

    if security_protocol != "PLAINTEXT":
        sasl_username = os.environ.get("KAFKA_API_KEY", "")
        sasl_password = os.environ.get("KAFKA_API_SECRET", "")
        if not sasl_username or not sasl_password:
            raise RuntimeError(
                f"KAFKA_SECURITY_PROTOCOL is {security_protocol!r} but "
                "KAFKA_API_KEY / KAFKA_API_SECRET are missing from infra/.env."
            )
        conf.update(
            {
                "security.protocol": security_protocol,
                "sasl.mechanisms": "PLAIN",
                "sasl.username": sasl_username,
                "sasl.password": sasl_password,
            }
        )
    return conf
