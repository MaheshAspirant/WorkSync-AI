"""Attendance capture, reconciliation and derived overtime."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import managed_team_ids
from app.audit.service import record_audit
from app.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.workforce import hours_between, week_start
from app.db.base import utcnow
from app.models.attendance import AttendanceEvent
from app.models.auth import User
from app.models.enums import (
    AttendanceStatus,
    ReconciliationStatus,
    RoleName,
)
from app.models.master import Employee, Shift
from app.models.scheduling import ShiftAssignment

ACTIVE_ASSIGNMENT_STATUSES = ["SCHEDULED", "CONFIRMED", "COMPLETED", "SWAPPED_IN"]
GRACE_MINUTES = 5


def _visible_attendance_stmt(db: Session, user: User):
    stmt = select(AttendanceEvent).options(
        joinedload(AttendanceEvent.employee),
        joinedload(AttendanceEvent.shift),
        joinedload(AttendanceEvent.assignment),
    )
    role = user.role_value
    if role in {RoleName.ADMIN, RoleName.HR}:
        return stmt
    if role == RoleName.MANAGER:
        teams = managed_team_ids(db, user)
        if not teams:
            return stmt.where(AttendanceEvent.attendance_id == "__none__")
        return stmt.join(Employee, Employee.employee_id == AttendanceEvent.employee_id).where(
            Employee.team_id.in_(teams)
        )
    return stmt.where(AttendanceEvent.employee_id == (user.employee_id or "__none__"))


def list_attendance(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 25,
    employee_id: str | None = None,
    status: AttendanceStatus | None = None,
    start: date | None = None,
    end: date | None = None,
) -> tuple[list[AttendanceEvent], int]:
    stmt = _visible_attendance_stmt(db, user)
    if employee_id:
        stmt = stmt.where(AttendanceEvent.employee_id == employee_id)
    if status:
        stmt = stmt.where(AttendanceEvent.status == status)
    if start:
        stmt = stmt.where(func.date(AttendanceEvent.scheduled_start) >= start)
    if end:
        stmt = stmt.where(func.date(AttendanceEvent.scheduled_start) <= end)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(AttendanceEvent.scheduled_start.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().scalars()
    )
    return rows, total


def _assert_employee_access(db: Session, user: User, employee_id: str) -> None:
    if user.role_value in {RoleName.ADMIN, RoleName.HR}:
        return
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise NotFoundError("Employee not found")
    if user.role_value == RoleName.MANAGER and employee.team_id in managed_team_ids(db, user):
        return
    if user.role_value == RoleName.EMPLOYEE and user.employee_id == employee_id:
        return
    raise PermissionDeniedError("You cannot record attendance for this employee")


def _derive_status(check_in: datetime | None, check_out: datetime | None,
                   scheduled_start: datetime, scheduled_end: datetime,
                   late_minutes: int, early_minutes: int) -> AttendanceStatus:
    if check_in is None:
        return AttendanceStatus.ABSENT
    if late_minutes > GRACE_MINUTES:
        return AttendanceStatus.LATE
    if check_out is None:
        return AttendanceStatus.ABSENT
    if early_minutes > 0:
        return AttendanceStatus.EARLY_DEPARTURE
    return AttendanceStatus.PRESENT


def _reconcat(attendance: AttendanceEvent) -> None:
    """Recompute derived fields from timestamps; never trust caller arithmetic."""
    if attendance.actual_check_in and attendance.actual_check_out:
        if attendance.actual_check_out < attendance.actual_check_in:
            raise ValidationError("check_out must be after check_in")
        attendance.actual_hours = round(
            hours_between(attendance.actual_check_in, attendance.actual_check_out), 2
        )
    else:
        attendance.actual_hours = 0.0
    scheduled_start = attendance.scheduled_start
    scheduled_end = attendance.scheduled_end
    if attendance.actual_check_in:
        delta = (attendance.actual_check_in - scheduled_start).total_seconds() / 60
        attendance.late_minutes = int(max(0, delta))
    else:
        attendance.late_minutes = 0
    if attendance.actual_check_out:
        delta = (scheduled_end - attendance.actual_check_out).total_seconds() / 60
        attendance.early_departure_minutes = int(max(0, delta))
    else:
        attendance.early_departure_minutes = 0
    employee = attendance.employee
    daily_cap = employee.daily_hours_cap if employee else 8.0
    attendance.overtime_hours = round(max(0.0, attendance.actual_hours - daily_cap), 2)
    if attendance.actual_check_in is None:
        attendance.status = AttendanceStatus.ABSENT
    else:
        attendance.status = _derive_status(
            attendance.actual_check_in,
            attendance.actual_check_out,
            scheduled_start,
            scheduled_end,
            attendance.late_minutes,
            attendance.early_departure_minutes,
        )


def create_attendance(db: Session, user: User, payload) -> AttendanceEvent:
    assignment = db.execute(
        select(ShiftAssignment)
        .options(
            joinedload(ShiftAssignment.shift),
            joinedload(ShiftAssignment.employee),
        )
        .where(ShiftAssignment.assignment_id == payload.assignment_id)
    ).unique().scalar_one_or_none()
    if assignment is None:
        raise NotFoundError("Assignment not found")
    _assert_employee_access(db, user, assignment.employee_id)
    if db.execute(
        select(AttendanceEvent).where(AttendanceEvent.assignment_id == assignment.assignment_id)
    ).scalar_one_or_none():
        raise ConflictError("Attendance already recorded for this assignment")
    if payload.check_in and payload.check_out and payload.check_out < payload.check_in:
        raise ValidationError("check_out must be after check_in")
    if payload.status in {AttendanceStatus.ABSENT, AttendanceStatus.NO_SHOW}:
        check_in = None
        check_out = None
    else:
        check_in = payload.check_in
        check_out = payload.check_out
    shift = assignment.shift
    if check_in is None:
        anchor = shift.start_at
    else:
        anchor = check_in
    attendance_id = f"ATT-{assignment.employee_id}-{anchor.strftime('%Y%m%dT%H%M%S')}"
    # Two shifts can share a check-in timestamp only in double-booking anomalies.
    suffix = 1
    base_id = attendance_id
    while db.get(AttendanceEvent, attendance_id) is not None:
        suffix += 1
        attendance_id = f"{base_id}-{suffix}"
    event = AttendanceEvent(
        attendance_id=attendance_id,
        employee_id=assignment.employee_id,
        shift_id=assignment.shift_id,
        assignment_id=assignment.assignment_id,
        scheduled_start=shift.start_at,
        scheduled_end=shift.end_at,
        actual_check_in=check_in,
        actual_check_out=check_out,
        status=payload.status or AttendanceStatus.PRESENT,
        late_minutes=0,
        early_departure_minutes=0,
        actual_hours=0.0,
        overtime_hours=0.0,
        source=payload.source,
        reconciliation_status=(
            ReconciliationStatus.MATCHED
            if assignment.status.value in ACTIVE_ASSIGNMENT_STATUSES
            else ReconciliationStatus.MISMATCH
        ),
        notes=payload.notes,
    )
    event.employee = assignment.employee
    _reconcat(event)
    if payload.status and payload.status in {AttendanceStatus.ABSENT, AttendanceStatus.NO_SHOW}:
        event.status = payload.status
    db.add(event)
    record_audit(db, user, "RECORD_ATTENDANCE", "AttendanceEvent", event.attendance_id,
                 new={"employee_id": event.employee_id, "shift_id": event.shift_id,
                      "status": event.status.value, "actual_hours": event.actual_hours,
                      "overtime_hours": event.overtime_hours})
    db.commit()
    return get_attendance(db, user, event.attendance_id)


def get_attendance(db: Session, user: User, attendance_id: str) -> AttendanceEvent:
    row = db.execute(
        _visible_attendance_stmt(db, user).where(AttendanceEvent.attendance_id == attendance_id)
    ).unique().scalar_one_or_none()
    if row is None:
        raise NotFoundError("Attendance event not found")
    return row


def update_attendance(db: Session, user: User, attendance_id: str, check_in: datetime | None,
                      check_out: datetime | None, notes: str | None) -> AttendanceEvent:
    event = get_attendance(db, user, attendance_id)
    previous = {
        "check_in": event.actual_check_in.isoformat() if event.actual_check_in else None,
        "check_out": event.actual_check_out.isoformat() if event.actual_check_out else None,
        "status": event.status.value,
        "actual_hours": event.actual_hours,
        "overtime_hours": event.overtime_hours,
    }
    event.actual_check_in = check_in
    event.actual_check_out = check_out
    if notes is not None:
        event.notes = notes
    _reconcat(event)
    event.reconciliation_status = (
        ReconciliationStatus.MATCHED
        if event.assignment and event.assignment.status.value in ACTIVE_ASSIGNMENT_STATUSES
        else ReconciliationStatus.MISMATCH
    )
    record_audit(db, user, "UPDATE_ATTENDANCE", "AttendanceEvent", attendance_id,
                 previous=previous,
                 new={"check_in": check_in.isoformat() if check_in else None,
                      "check_out": check_out.isoformat() if check_out else None,
                      "status": event.status.value, "actual_hours": event.actual_hours,
                      "overtime_hours": event.overtime_hours})
    db.commit()
    return get_attendance(db, user, attendance_id)


# ------------------------------------------------------------------ overtime


def weekly_overtime_rows(
    db: Session,
    *,
    start: date,
    end: date,
    employee_id: str | None = None,
    team_id: str | None = None,
) -> list[dict]:
    """Weekly overtime derived from attendance and assignment records.

    Overtime is the amount of *actual* hours above the employee's weekly
    standard cap.  It is never generated independently of attendance.
    """
    stmt = (
        select(
            AttendanceEvent.employee_id,
            Employee.first_name,
            Employee.last_name,
            Employee.team_id,
            Employee.weekly_hours_cap,
            Employee.overtime_cap_weekly,
            AttendanceEvent.scheduled_start,
            AttendanceEvent.actual_hours,
        )
        .join(Employee, Employee.employee_id == AttendanceEvent.employee_id)
        .where(
            func.date(AttendanceEvent.scheduled_start) >= start,
            func.date(AttendanceEvent.scheduled_start) <= end,
        )
    )
    if employee_id:
        stmt = stmt.where(AttendanceEvent.employee_id == employee_id)
    if team_id:
        stmt = stmt.where(Employee.team_id == team_id)
    rows = db.execute(stmt).all()
    buckets: dict[tuple[str, date], dict] = {}
    for row in rows:
        monday = week_start(row.scheduled_start.date())
        key = (row.employee_id, monday)
        bucket = buckets.setdefault(
            key,
            {
                "employee_id": row.employee_id,
                "employee_name": f"{row.first_name} {row.last_name}",
                "team_id": row.team_id,
                "week_start": monday,
                "scheduled_hours": 0.0,
                "actual_hours": 0.0,
                "overtime_cap": row.overtime_cap_weekly,
            },
        )
        bucket["actual_hours"] += float(row.actual_hours or 0.0)
    # Scheduled hours come from assignments, including future shifts in the week.
    scheduled_rows = db.execute(
        select(
            ShiftAssignment.employee_id,
            Shift.shift_date,
            ShiftAssignment.scheduled_hours,
        )
        .join(Shift, Shift.shift_id == ShiftAssignment.shift_id)
        .where(
            Shift.shift_date >= start,
            Shift.shift_date <= end,
            ShiftAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
        )
    ).all()
    for employee, shift_date, hours in scheduled_rows:
        key = (employee, week_start(shift_date))
        if key in buckets:
            buckets[key]["scheduled_hours"] += float(hours or 0.0)
    result = []
    for bucket in buckets.values():
        employee = db.get(Employee, bucket["employee_id"])
        weekly_cap = employee.weekly_hours_cap if employee else 40.0
        overtime = round(max(0.0, bucket["actual_hours"] - weekly_cap), 2)
        bucket["overtime_hours"] = overtime
        bucket["cap_exceeded"] = overtime > bucket["overtime_cap"]
        result.append(bucket)
    result.sort(key=lambda r: (r["week_start"], r["employee_id"]))
    return result


def attendance_summary(db: Session, user: User, employee_id: str, start: date, end: date) -> dict:
    _assert_employee_access(db, user, employee_id)
    events = list(
        db.execute(
            select(AttendanceEvent).where(
                AttendanceEvent.employee_id == employee_id,
                func.date(AttendanceEvent.scheduled_start) >= start,
                func.date(AttendanceEvent.scheduled_start) <= end,
            )
        ).scalars()
    )
    scheduled = sum(e.scheduled_end.timestamp() - e.scheduled_start.timestamp() for e in events)
    scheduled_hours = round(scheduled / 3600, 2) if events else 0.0
    actual_hours = round(sum(e.actual_hours for e in events), 2)
    over_rows = weekly_overtime_rows(db, start=start, end=end, employee_id=employee_id)
    overtime = round(sum(r["overtime_hours"] for r in over_rows), 2)
    absent = sum(1 for e in events if e.status in {AttendanceStatus.ABSENT, AttendanceStatus.NO_SHOW})
    return {
        "employee_id": employee_id,
        "period_start": start,
        "period_end": end,
        "scheduled_shifts": len(events),
        "attended_shifts": sum(1 for e in events if e.actual_check_in is not None),
        "absent_shifts": absent,
        "late_events": sum(1 for e in events if e.status == AttendanceStatus.LATE),
        "total_scheduled_hours": scheduled_hours,
        "total_actual_hours": actual_hours,
        "total_overtime_hours": overtime,
        "absence_rate": round(absent / len(events) * 100, 2) if events else 0.0,
    }
