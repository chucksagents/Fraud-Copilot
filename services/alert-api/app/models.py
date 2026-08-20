"""
ORM models.

Alert  -- mirrors docs/schemas/fraud-alert.schema.json. Written only by the
          Kafka consumer (kafka_consumer.py); the API never mutates alerts.
Case   -- opened 1:1 with an alert the moment it's ingested. Kept as its own
          table (rather than just reusing alert_id as the case id) so a
          future version can support one case spanning multiple related
          alerts without an API/schema change.
CaseAction -- mirrors docs/schemas/case-action.schema.json. Written by
          POST /cases/{case_id}/actions and republished to case-actions.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(String, primary_key=True)
    generated_at: Mapped[str] = mapped_column(String, nullable=False)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    account_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rule_triggered: Mapped[str] = mapped_column(String, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    related_event_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="new")
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.utcnow
    )

    case: Mapped[Optional["Case"]] = relationship(back_populates="alert", uselist=False)


class Case(Base):
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    alert_id: Mapped[str] = mapped_column(
        String, ForeignKey("alerts.alert_id"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.utcnow
    )

    alert: Mapped["Alert"] = relationship(back_populates="case")
    actions: Mapped[list["CaseAction"]] = relationship(back_populates="case")


class CaseAction(Base):
    __tablename__ = "case_actions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(
        String, ForeignKey("cases.case_id"), nullable=False, index=True
    )
    alert_id: Mapped[str] = mapped_column(String, nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.utcnow
    )
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    case: Mapped["Case"] = relationship(back_populates="actions")
