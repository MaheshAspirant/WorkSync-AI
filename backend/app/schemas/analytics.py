"""Analytics response schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    total_employees: int
    active_employees: int
    total_teams: int
    total_shifts: int
    total_assignments: int
    total_leave_requests: int
    approved_leave_requests: int
    pending_leave_requests: int
    rejected_leave_requests: int
    coverage_pct: float
    skill_coverage_pct: float
    total_overtime_hours: float
    avg_overtime_per_employee: float
    absence_rate: float
    conflict_count: int
    open_conflict_count: int
    fairness_score: float
    schedule_validity_pct: float
    period_start: date
    period_end: date


class CoverageAnalytics(BaseModel):
    period_start: date
    period_end: date
    required_positions: int
    filled_positions: int
    coverage_pct: float
    skill_required_positions: int
    skill_filled_positions: int
    skill_coverage_pct: float
    by_team: list[dict]
    by_day: list[dict]
    top_gaps: list[dict]


class OvertimeAnalytics(BaseModel):
    period_start: date
    period_end: date
    total_overtime_hours: float
    average_overtime_per_employee: float
    employees_over_cap: int
    by_week: list[dict]
    by_team: list[dict]
    top_employees: list[dict]


class FairnessAnalytics(BaseModel):
    period_start: date
    period_end: date
    fairness_score: float
    night_shift_score: float
    weekend_shift_score: float
    overtime_score: float
    by_employee: list[dict]
    explanation: str


class LeaveAnalytics(BaseModel):
    period_start: date
    period_end: date
    by_status: list[dict]
    by_type: list[dict]
    by_month: list[dict]
    approval_rate: float


class TrendAnalytics(BaseModel):
    period_start: date
    period_end: date
    coverage: list[dict]
    overtime: list[dict]
    absences: list[dict]


class ActivityItem(BaseModel):
    audit_id: int
    actor_role: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    created_at: str


class ActivityFeed(BaseModel):
    items: list[ActivityItem]
