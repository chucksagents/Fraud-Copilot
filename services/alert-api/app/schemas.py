"""
Pydantic request/response models for the API layer. Kept separate from the
ORM models (models.py) on purpose -- request/response shape and storage
shape are allowed to drift.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Kept in sync by hand with docs/schemas/case-action.schema.json's enums.
ActionType = Literal["card_lock", "contact_customer", "no_action", "escalate"]
ActionStatus = Literal["recommended", "approved", "rejected", "executed"]


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: str
    generated_at: str
    customer_id: str
    account_id: Optional[str]
    rule_triggered: str
    severity: str
    related_event_ids: list[str]
    evidence: dict[str, Any]
    status: str
    case_id: Optional[str] = None  # populated from the joined Case row, not a DB column


class CaseActionCreate(BaseModel):
    action_type: ActionType
    status: ActionStatus = "recommended"
    actor: str = Field(..., description="agent_id for an agent, or analyst_id for a human")
    notes: Optional[str] = None


class CaseActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    alert_id: str
    action_type: str
    status: str
    actor: str
    timestamp: dt.datetime
    notes: Optional[str]
