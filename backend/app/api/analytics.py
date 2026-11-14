"""Analytics and report endpoints."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    db_session,
    get_current_employee,
    get_current_user,
    require_roles,
)
from app.models.auth import User
from app.models.enums import RoleName
from app.models.master import Employee
from app.schemas.analytics import (
    CoverageAnalytics,
    DashboardMetrics,
    FairnessAnalytics,
    LeaveAnalytics,
    OvertimeAnalytics,
    TrendAnalytics,
)
from app.services import analytics_service, attendance_service, leave_service, scheduling_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])

ANALYST = (RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)


@router.get("/dashboard", response_model=DashboardMetrics)
def dashboard(
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(require_roles(*ANALYST)),
    db: Session = Depends(db_session),
):
    return analytics_service.dashboard(db, start, end)


@router.get("/coverage", response_model=CoverageAnalytics)
def coverage(
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(require_roles(*ANALYST)),
    db: Session = Depends(db_session),
):
    return analytics_service.coverage_analytics(db, start, end)


@router.get("/overtime", response_model=OvertimeAnalytics)
def overtime(
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(require_roles(*ANALYST)),
    db: Session = Depends(db_session),
):
    return analytics_service.overtime_analytics(db, start, end)


@router.get("/fairness", response_model=FairnessAnalytics)
def fairness(
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(require_roles(*ANALYST)),
    db: Session = Depends(db_session),
):
    return analytics_service.fairness_analytics(db, start, end)


@router.get("/leave", response_model=LeaveAnalytics)
def leave(
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(require_roles(*ANALYST)),
    db: Session = Depends(db_session),
):
    return analytics_service.leave_analytics(db, start, end)


@router.get("/trends", response_model=TrendAnalytics)
def trends(
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(require_roles(*ANALYST)),
    db: Session = Depends(db_session),
):
    return analytics_service.trends(db, start, end)


@router.get("/me")
def my_dashboard(
    employee: Employee = Depends(get_current_employee),
    db: Session = Depends(db_session),
):
    today = date.today()
    start, end = analytics_service.default_period(db, None, None)
    assignments, _ = scheduling_service.list_assignments(
        db, _user_from_employee(employee), page=1, page_size=200,
        employee_id=employee.employee_id, start=today, end=today + timedelta(days=30),
    )
    summary = attendance_service.attendance_summary(
        db, _user_from_employee(employee), employee.employee_id, start, end
    )
    balances = leave_service.leave_balances(db, employee.employee_id, today.year)
    overtime_rows = attendance_service.weekly_overtime_rows(
        db, start=start, end=end, employee_id=employee.employee_id
    )
    return {
        "employee_id": employee.employee_id,
        "employee_name": employee.full_name,
        "team_id": employee.team_id,
        "team_name": employee.team_name,
        "preferred_shift": employee.preferred_shift.value,
        "weekly_hours_cap": employee.weekly_hours_cap,
        "overtime_cap_weekly": employee.overtime_cap_weekly,
        "upcoming_assignments": [
            {
                "assignment_id": a.assignment_id,
                "shift_id": a.shift_id,
                "shift_date": a.shift_date,
                "template_code": a.template_code,
                "start_at": a.start_at,
                "end_at": a.end_at,
                "scheduled_hours": a.scheduled_hours,
            }
            for a in assignments
        ],
        "attendance_summary": summary,
        "leave_balances": balances,
        "overtime_weeks": overtime_rows,
    }


def _user_from_employee(employee: Employee) -> User:
    """Build a lightweight principal for reuse of employee-scoped services."""
    class _Principal:
        employee_id = employee.employee_id
        role_value = RoleName.EMPLOYEE
        user_id = None
        role = None

    return _Principal()  # type: ignore[return-value]
