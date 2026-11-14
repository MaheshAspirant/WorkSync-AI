"""Leave-management schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LeaveStatus, LeaveType


class LeaveCreate(BaseModel):
    employee_id: str | None = None  # managers/HR may file on behalf of an employee
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=500)


class LeaveDecisionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


class LeaveHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    history_id: int
    from_status: LeaveStatus | None = None
    to_status: LeaveStatus
    action: str
    actor_user_id: str | None = None
    comment: str | None = None
    created_at: datetime


class LeaveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    leave_id: str
    employee_id: str
    employee_name: str | None = None
    team_id: str | None = None
    leave_type: LeaveType
    policy_id: str
    start_date: date
    end_date: date
    total_days: float
    reason: str
    status: LeaveStatus
    submitted_at: datetime
    decided_at: datetime | None = None
    decided_by_user_id: str | None = None
    manager_comment: str | None = None
    history: list[LeaveHistoryOut] = []


class LeavePolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_id: str
    leave_type: str
    annual_entitlement_days: float
    max_consecutive_days: int
    requires_document_after_days: int | None = None
    is_paid: bool
    min_notice_days: int
    description: str | None = None


class LeaveBalanceOut(BaseModel):
    leave_type: LeaveType
    entitlement_days: float
    approved_days: float
    pending_days: float
    remaining_days: float


class LeaveBalanceResponse(BaseModel):
    employee_id: str
    year: int
    balances: list[LeaveBalanceOut]
