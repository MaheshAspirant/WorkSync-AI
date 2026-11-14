"""Attendance and overtime endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_current_user, require_roles
from app.models.auth import User
from app.models.enums import AttendanceStatus, RoleName
from app.schemas.attendance import (
    AttendanceCreate,
    AttendanceOut,
    AttendanceSummary,
    AttendanceUpdate,
    OvertimeSummary,
)
from app.schemas.common import Page
from app.services import attendance_service

router = APIRouter(tags=["Attendance & Overtime"])


@router.get("/attendance", response_model=Page[AttendanceOut])
def list_attendance(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    employee_id: str | None = None,
    status_filter: AttendanceStatus | None = Query(None, alias="status"),
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    rows, total = attendance_service.list_attendance(
        db, user, page=page, page_size=page_size, employee_id=employee_id,
        status=status_filter, start=start, end=end,
    )
    return Page.build(rows, total, page, page_size)


@router.get("/attendance/overtime", response_model=OvertimeSummary)
def overtime(
    start: date | None = None,
    end: date | None = None,
    employee_id: str | None = None,
    team_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    if user.role_value == RoleName.EMPLOYEE:
        employee_id = user.employee_id
    if start is None or end is None:
        from app.services.analytics_service import default_period
        start, end = default_period(db, start, end)
    rows = attendance_service.weekly_overtime_rows(
        db, start=start, end=end, employee_id=employee_id, team_id=team_id
    )
    total = round(sum(r["overtime_hours"] for r in rows), 2)
    employees = {r["employee_id"] for r in rows}
    return {
        "period_start": start,
        "period_end": end,
        "total_overtime_hours": total,
        "average_overtime_per_employee": round(total / len(employees), 2) if employees else 0.0,
        "employees_over_cap": len({r["employee_id"] for r in rows if r["cap_exceeded"]}),
        "rows": rows,
    }


@router.get("/attendance/summary/{employee_id}", response_model=AttendanceSummary)
def summary(
    employee_id: str,
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    if start is None or end is None:
        from app.services.analytics_service import default_period
        start, end = default_period(db, start, end)
    return attendance_service.attendance_summary(db, user, employee_id, start, end)


@router.post("/attendance", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def create_attendance(
    payload: AttendanceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    return attendance_service.create_attendance(db, user, payload)


@router.get("/attendance/{attendance_id}", response_model=AttendanceOut)
def get_attendance(
    attendance_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    return attendance_service.get_attendance(db, user, attendance_id)


@router.put("/attendance/{attendance_id}", response_model=AttendanceOut)
def update_attendance(
    attendance_id: str,
    payload: AttendanceUpdate,
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    return attendance_service.update_attendance(
        db, user, attendance_id, payload.check_in, payload.check_out, payload.notes
    )
