"""Scheduling, coverage and exception schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    IssueType,
    ResolutionStatus,
    RunStatus,
    Severity,
    SolverStatus,
)


class GenerateScheduleRequest(BaseModel):
    team_id: str | None = None
    start_date: date
    end_date: date
    replace_existing: bool = False
    time_limit_seconds: float | None = Field(default=None, ge=1, le=120)
    use_preferences: bool = True
    use_fairness: bool = True


class SchedulingDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_id: int
    run_id: str
    shift_id: str
    employee_id: str
    employee_name: str | None = None
    shift_date: date | None = None
    template_code: str | None = None
    assignment_id: str | None = None
    reason: str
    skill_match: bool
    availability_result: str
    leave_eligible: bool
    constraint_evaluation: dict
    optimization_score: float
    created_at: datetime


class SchedulingRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    team_id: str | None = None
    team_name: str | None = None
    scope_start: date
    scope_end: date
    status: RunStatus
    solver_status: SolverStatus
    objective_value: float | None = None
    assignments_created: int
    coverage_gaps: int
    hard_violations: int
    soft_score: float | None = None
    duration_seconds: float | None = None
    parameters: dict = {}
    started_at: datetime
    completed_at: datetime | None = None
    message: str | None = None
    decisions: list[SchedulingDecisionOut] = []
    exceptions: list["ExceptionOut"] = []


class SchedulingRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    team_id: str | None = None
    team_name: str | None = None
    scope_start: date
    scope_end: date
    status: RunStatus
    solver_status: SolverStatus
    assignments_created: int
    coverage_gaps: int
    duration_seconds: float | None = None
    started_at: datetime
    completed_at: datetime | None = None


class ExceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    issue_id: str
    run_id: str | None = None
    issue_type: IssueType
    employee_id: str | None = None
    employee_name: str | None = None
    shift_id: str | None = None
    shift_date: date | None = None
    assignment_id: str | None = None
    transaction_type: str | None = None
    transaction_id: str | None = None
    severity: Severity
    description: str
    detection_source: str
    resolution_status: ResolutionStatus
    detected_at: datetime
    resolved_by_user_id: str | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None


class ResolveExceptionRequest(BaseModel):
    resolution_status: ResolutionStatus = ResolutionStatus.RESOLVED
    note: str | None = Field(default=None, max_length=500)


class DetectionSummary(BaseModel):
    detected: int
    new: int
    updated: int
    by_type: dict[str, int]
    run_id: str | None = None


class CoverageRequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    coverage_id: str
    team_id: str
    shift_template_id: str
    skill_id: str | None = None
    skill_name: str | None = None
    day_type: str
    min_staff: int
    effective_from: date
    effective_to: date | None = None


class CoverageGapOut(BaseModel):
    shift_id: str
    team_id: str
    shift_date: date
    template_code: str
    required: int
    assigned: int
    gap: int
    missing_skills: list[str] = []


SchedulingRunOut.model_rebuild()
