"""Pydantic API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- health ---


class HealthResponse(BaseModel):
    status: str
    env: str
    dry_run: bool
    checks: dict


# --- opportunities ---


class OpportunityOut(ORMModel):
    id: uuid.UUID
    source: str
    source_id: str
    topic: str
    url: str
    engagement: dict
    trend: dict
    discovered_at: datetime


class ScoreRequest(BaseModel):
    opportunity_id: uuid.UUID
    factors: dict[str, float]
    penalties: dict[str, float] | None = None


# --- content ---


class ContentItemOut(ORMModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    title: str
    state: str
    human_review_required: bool
    created_at: datetime


class TransitionRequest(BaseModel):
    to_state: str
    reason: str = ""


# --- safety ---


class SafetyRequest(BaseModel):
    state: str = Field(pattern="^(RUNNING|PAUSED|EMERGENCY_STOP)$")


# --- review ---


class ReviewActionRequest(BaseModel):
    action: str = Field(pattern="^(APPROVE|REJECT|EDIT|REGENERATE|RETRY|ESCALATE)$")
    note: str = ""
    actor: str = "operator"


# --- budget ---


class BudgetUpdateRequest(BaseModel):
    budgets: dict[str, float]
