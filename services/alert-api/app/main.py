"""
Fraud alert/case API.

Consumes `fraud-alerts` from Kafka in a background thread (kafka_consumer.py),
persists each alert and an auto-opened case for it into SQLite
(ALERT_API_DB_URL), and exposes:

  GET  /alerts
  GET  /alerts/{alert_id}
  POST /cases/{case_id}/actions

See README.md in this directory for how to run it locally.
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import kafka_consumer, kafka_producer
from .db import get_db, init_db
from .models import Alert, Case, CaseAction
from .schemas import AlertOut, CaseActionCreate, CaseActionOut

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alert_api")

_stop_event = threading.Event()
_consumer_thread: Optional[threading.Thread] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    global _consumer_thread
    _consumer_thread = kafka_consumer.start(_stop_event)
    logger.info("fraud-alerts consumer thread started")
    yield
    _stop_event.set()
    if _consumer_thread is not None:
        _consumer_thread.join(timeout=5)
    logger.info("fraud-alerts consumer thread stopped")


app = FastAPI(title="Fraud Alert & Case API", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    customer_id: Optional[str] = Query(default=None),
    rule_triggered: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Alert)
    if customer_id:
        stmt = stmt.where(Alert.customer_id == customer_id)
    if rule_triggered:
        stmt = stmt.where(Alert.rule_triggered == rule_triggered)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    stmt = stmt.order_by(Alert.ingested_at.desc()).offset(offset).limit(limit)

    alerts = db.execute(stmt).scalars().all()
    return [_to_alert_out(a) for a in alerts]


@app.get("/alerts/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: str, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"alert {alert_id} not found")
    return _to_alert_out(alert)


@app.post("/cases/{case_id}/actions", response_model=CaseActionOut, status_code=201)
def create_case_action(case_id: str, body: CaseActionCreate, db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"case {case_id} not found")

    action = CaseAction(
        case_id=case.case_id,
        alert_id=case.alert_id,
        action_type=body.action_type,
        status=body.status,
        actor=body.actor,
        notes=body.notes,
    )
    db.add(action)

    # Simple demo-level heuristic: an executed action closes the case. Easy
    # to rip out or replace with a real state machine later.
    if body.status == "executed":
        case.status = "closed"

    db.commit()
    db.refresh(action)

    try:
        kafka_producer.publish_case_action(
            {
                "case_id": action.case_id,
                "alert_id": action.alert_id,
                "action_type": action.action_type,
                "status": action.status,
                "actor": action.actor,
                "timestamp": action.timestamp.isoformat() + "Z",
                "notes": action.notes,
            }
        )
    except Exception:
        # Don't fail the request if Kafka is unreachable -- the action is
        # already durably stored in SQLite. Log loudly so it's noticed.
        logger.exception("failed to publish case action %s to Kafka", action.id)

    return action


def _to_alert_out(alert: Alert) -> AlertOut:
    out = AlertOut.model_validate(alert)
    out.case_id = alert.case.case_id if alert.case else None
    return out
