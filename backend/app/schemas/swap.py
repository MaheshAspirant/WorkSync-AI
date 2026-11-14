"""Shift-swap schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SwapStatus


class SwapCreate(BaseModel):
    requester_assignment_id: str
    target_assignment_id: str
    reason: str = Field(min_length=3, max_length=500)


class SwapActionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


class SwapTargetResponse(BaseModel):
    agree: bool
    comment: str | None = Field(default=None, max_length=500)


class SwapHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    history_id: int
    from_status: SwapStatus | None = None
    to_status: SwapStatus
    action: str
    actor_user_id: str | None = None
    comment: str | None = None
    created_at: datetime


class SwapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    swap_id: str
    requester_employee_id: str
    requester_name: str | None = None
    target_employee_id: str
    target_name: str | None = None
    requester_assignment_id: str
    target_assignment_id: str
    requester_shift_date: date | None = None
    target_shift_date: date | None = None
    requester_shift_code: str | None = None
    target_shift_code: str | None = None
    reason: str
    status: SwapStatus
    requester_agreed: bool
    target_agreed: bool
    target_responded_at: datetime | None = None
    manager_user_id: str | None = None
    decided_at: datetime | None = None
    decision_comment: str | None = None
    applied_at: datetime | None = None
    created_at: datetime
    history: list[SwapHistoryOut] = []
