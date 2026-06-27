"""
models.py — Strict Pydantic schemas for the Memory module.
All outputs flowing out of the Memory module must conform to these types.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Entity models (mirror DB tables)
# ─────────────────────────────────────────────

class Goal(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    priority: Optional[Literal["high", "medium", "low"]] = None
    created_at: Optional[datetime] = None


class Task(BaseModel):
    id: str
    title: str
    status: Optional[Literal["pending", "completed", "overdue"]] = None
    due_date: Optional[datetime] = None
    goal_id: Optional[str] = None
    created_at: Optional[datetime] = None


class Event(BaseModel):
    id: str
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: Optional[datetime] = None


class Contact(BaseModel):
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    last_interaction: Optional[datetime] = None
    importance_score: float = 0.0


class BehaviorPattern(BaseModel):
    id: str
    pattern_type: Optional[str] = None
    description: Optional[str] = None
    confidence: Optional[float] = None
    last_updated: Optional[datetime] = None


class GoalAlignment(BaseModel):
    id: str
    goal_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    alignment_score: Optional[float] = None
    last_updated: Optional[datetime] = None


class UserAction(BaseModel):
    id: str
    action_type: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    metadata: Optional[str] = None
    created_at: Optional[datetime] = None


# ─────────────────────────────────────────────
# UserContext — the strict output schema
# ─────────────────────────────────────────────

class UserContext(BaseModel):
    """Strict output schema returned by build_user_context()."""

    user_id: str = Field(..., description="Unique user identifier")
    goals: list[Goal] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    contacts: list[Contact] = Field(default_factory=list)
    behavior_patterns: list[BehaviorPattern] = Field(default_factory=list)
    goal_alignments: list[GoalAlignment] = Field(default_factory=list)
    recent_actions: list[UserAction] = Field(default_factory=list)
    built_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
