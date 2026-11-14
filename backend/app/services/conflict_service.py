"""Detect scheduling exceptions from persisted operational records.

The detector never reads ground-truth labels.  It derives every finding from
assignments, leave, coverage requirements, skills, attendance and swap history.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.errors import NotFoundError
from app.core.ids import next_id
from app.core.workforce import classify_day, rest_gap_hours, overlaps, week_start
from app.db.base import utcnow
from app.models.attendance import AttendanceEvent
from app.models.auth import User
from app.models.enums import (
    AssignmentStatus,
    DayType,
    IssueType,
    LeaveStatus,
    ResolutionStatus,
    RoleName,
    Severity,
    SwapStatus,
)
from app.models.leave import LeaveApprovalHistory, LeaveRequest
from app.models.master import Employee, EmployeeSkill, HolidayCalendar, Shift
from app.models.scheduling import (
    CoverageRequirement,
    SchedulingException,
    ShiftAssignment,
    SwapApprovalHistory,
    SwapRequest,
)
from app.services.attendance_service import weekly_overtime_rows

ACTIVE_STATUSES = [
    AssignmentStatus.SCHEDULED,
    AssignmentStatus.CONFIRMED,
    AssignmentStatus.COMPLETED,
    AssignmentStatus.SWAPPED_IN,
]

SEVERITY = {
    IssueType.DOUBLE_BOOKING: Severity.CRITICAL,
    IssueType.LEAVE_OVERLAP: Severity.HIGH,
    IssueType.MISSING_SKILL: Severity.HIGH,
    IssueType.OVERTIME_CAP: Severity.MEDIUM,
    IssueType.UNAPPROVED_SWAP: Severity.CRITICAL,
    IssueType.COVERAGE_GAP: Severity.HIGH,
    IssueType.REST_VIOLATION: Severity.MEDIUM,
    IssueType.HOURS_CAP: Severity.HIGH,
    IssueType.ATTENDANCE_MISMATCH: Severity.LOW,
    IssueType.INVALID_ASSIGNMENT: Severity.HIGH,
}


def _fingerprint(kind: IssueType, employee_id, shift_id, assignment_id, transaction_id) -> str:
    return "|".join(
        [
            kind.value,
            employee_id or "-",
            shift_id or "-",
            assignment_id or "-",
            transaction_id or "-",
        ]
    )[:220]


def _draft(kind: IssueType, description: str, *, employee_id=None, shift_id=None,
           assignment_id=None, transaction_type=None, transaction_id=None,
           severity: Severity | None = None) -> dict:
    return {
        "issue_type": kind,
        "employee_id": employee_id,
        "shift_id": shift_id,
        "assignment_id": assignment_id,
        "transaction_type": transaction_type,
        "transaction_id": transaction_id,
        "severity": severity or SEVERITY[kind],
        "description": description,
        "fingerprint": _fingerprint(kind, employee_id, shift_id, assignment_id, transaction_id),
    }


def _active_assignment_rows(db: Session, start: date | None, end: date | None):
    stmt = (
        select(
            ShiftAssignment.assignment_id,
            ShiftAssignment.employee_id,
            ShiftAssignment.shift_id,
            ShiftAssignment.status,
            Shift.shift_date,
            Shift.start_at,
            Shift.end_at,
            Shift.team_id,
        )
        .join(Shift, Shift.shift_id == ShiftAssignment.shift_id)
        .where(ShiftAssignment.status.in_(ACTIVE_STATUSES))
    )
    if start:
        stmt = stmt.where(Shift.shift_date >= start)
    if end:
        stmt = stmt.where(Shift.shift_date <= end)
    return db.execute(stmt.order_by(Shift.start_at)).all()


def _detect_double_booking(db: Session, start, end) -> list[dict]:
    rows = _active_assignment_rows(db, start, end)
    by_employee: dict[str, list] = {}
    for row in rows:
        by_employee.setdefault(row.employee_id, []).append(row)
    issues = []
    for employee_id, assignments in by_employee.items():
        ordered = sorted(assignments, key=lambda r: (r.start_at, r.assignment_id))
        for index, first in enumerate(ordered):
            for second in ordered[index + 1:]:
                if second.start_at >= first.end_at:
                    break
                if overlaps(first.start_at, first.end_at, second.start_at, second.end_at):
                    issues.append(
                        _draft(
                            IssueType.DOUBLE_BOOKING,
                            f"Employee {employee_id} is assigned to overlapping shifts "
                            f"{first.shift_id} and {second.shift_id}.",
                            employee_id=employee_id,
                            shift_id=second.shift_id,
                            assignment_id=second.assignment_id,
                            transaction_type="ASSIGNMENT",
                            transaction_id=first.assignment_id,
                        )
                    )
    return issues


def _detect_leave_overlap(db: Session, start, end) -> list[dict]:
    stmt = (
        select(
            ShiftAssignment.assignment_id,
            ShiftAssignment.employee_id,
            ShiftAssignment.shift_id,
            Shift.shift_date,
            LeaveRequest.leave_id,
        )
        .join(Shift, Shift.shift_id == ShiftAssignment.shift_id)
        .join(
            LeaveRequest,
            and_(
                LeaveRequest.employee_id == ShiftAssignment.employee_id,
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.start_date <= Shift.shift_date,
                LeaveRequest.end_date >= Shift.shift_date,
            ),
        )
        .where(ShiftAssignment.status.in_(ACTIVE_STATUSES))
    )
    if start:
        stmt = stmt.where(Shift.shift_date >= start)
    if end:
        stmt = stmt.where(Shift.shift_date <= end)
    issues = []
    for row in db.execute(stmt).all():
        issues.append(
            _draft(
                IssueType.LEAVE_OVERLAP,
                f"Employee {row.employee_id} is assigned to shift {row.shift_id} on "
                f"{row.shift_date} which falls inside approved leave {row.leave_id}.",
                employee_id=row.employee_id,
                shift_id=row.shift_id,
                assignment_id=row.assignment_id,
                transaction_type="LEAVE",
                transaction_id=row.leave_id,
            )
        )
    return issues


def _coverage_snapshot(db: Session, start, end):
    shifts = db.execute(
        select(
            Shift.shift_id,
            Shift.team_id,
            Shift.shift_template_id,
            Shift.shift_date,
            Shift.required_staff,
        ).where(
            Shift.shift_date >= start,
            Shift.shift_date <= end,
        )
    ).all()
    assignments = db.execute(
        select(
            ShiftAssignment.shift_id,
            ShiftAssignment.employee_id,
            ShiftAssignment.assignment_id,
        ).where(ShiftAssignment.status.in_(ACTIVE_STATUSES))
    ).all()
    assigned: dict[str, list[tuple[str, str]]] = {}
    for shift_id, employee_id, assignment_id in assignments:
        assigned.setdefault(shift_id, []).append((employee_id, assignment_id))
    requirements = db.execute(
        select(CoverageRequirement).where(
            CoverageRequirement.effective_from <= end,
            (CoverageRequirement.effective_to.is_(None))
            | (CoverageRequirement.effective_to >= start),
        )
    ).scalars().all()
    skills_by_employee: dict[str, set[str]] = {}
    for employee_id, skill_id in db.execute(select(EmployeeSkill.employee_id, EmployeeSkill.skill_id)):
        skills_by_employee.setdefault(employee_id, set()).add(skill_id)
    holidays = set(
        db.execute(
            select(HolidayCalendar.holiday_date).where(
                HolidayCalendar.holiday_date >= start, HolidayCalendar.holiday_date <= end
            )
        ).scalars()
    )
    return shifts, assigned, requirements, skills_by_employee, holidays


def _detect_coverage_and_skills(db: Session, start, end) -> list[dict]:
    shifts, assigned, requirements, skills_by_employee, holidays = _coverage_snapshot(
        db, start, end
    )
    req_by_key: dict[tuple, list[CoverageRequirement]] = {}
    for req in requirements:
        req_by_key.setdefault((req.team_id, req.shift_template_id), []).append(req)
    issues: list[dict] = []
    for shift in shifts:
        assigned_rows = assigned.get(shift.shift_id, [])
        if not assigned_rows:
            # An empty shift is one coverage-gap exception, not one missing-skill
            # exception per required skill.
            issues.append(
                _draft(
                    IssueType.COVERAGE_GAP,
                    f"Shift {shift.shift_id} requires {shift.required_staff} staff but has "
                    f"0 active assignment(s).",
                    shift_id=shift.shift_id,
                    transaction_type="TEAM",
                    transaction_id=shift.team_id,
                )
            )
            continue
        if len(assigned_rows) < shift.required_staff:
            issues.append(
                _draft(
                    IssueType.COVERAGE_GAP,
                    f"Shift {shift.shift_id} requires {shift.required_staff} staff but has "
                    f"{len(assigned_rows)} active assignment(s).",
                    shift_id=shift.shift_id,
                    transaction_type="TEAM",
                    transaction_id=shift.team_id,
                )
            )
            # A headcount gap is the primary finding; do not also emit a
            # missing-skill exception for every requirement on that shift.
            continue
        day_type = classify_day(shift.shift_date, holidays)
        applicable = [
            r
            for r in req_by_key.get((shift.team_id, shift.shift_template_id), [])
            if r.day_type in {DayType.ALL, day_type}
            and r.effective_from <= shift.shift_date
            and (r.effective_to is None or r.effective_to >= shift.shift_date)
        ]
        for req in applicable:
            if not req.skill_id:
                continue
            qualified = sum(
                1 for employee_id, _ in assigned_rows
                if req.skill_id in skills_by_employee.get(employee_id, set())
            )
            if qualified < req.min_staff:
                issues.append(
                    _draft(
                        IssueType.MISSING_SKILL,
                        f"Shift {shift.shift_id} needs {req.min_staff} employee(s) with "
                        f"{req.skill_id}; only {qualified} qualified employee(s) assigned.",
                        shift_id=shift.shift_id,
                        transaction_type="SKILL",
                        transaction_id=req.skill_id,
                    )
                )
    return issues


def _detect_overtime(db: Session, start, end) -> list[dict]:
    issues = []
    for row in weekly_overtime_rows(db, start=start, end=end):
        if not row["cap_exceeded"]:
            continue
        issues.append(
            _draft(
                IssueType.OVERTIME_CAP,
                f"Employee {row['employee_id']} recorded {row['overtime_hours']:.1f}h overtime in "
                f"week {row['week_start']} (cap {row['overtime_cap']:.1f}h).",
                employee_id=row["employee_id"],
                transaction_type="WEEK",
                transaction_id=str(row["week_start"]),
            )
        )
    return issues


def _detect_unapproved_swaps(db: Session, start, end) -> list[dict]:
    swaps = db.execute(
        select(SwapRequest).where(SwapRequest.status == SwapStatus.APPLIED)
    ).scalars().all()
    issues = []
    for swap in swaps:
        approved = db.execute(
            select(SwapApprovalHistory).where(
                SwapApprovalHistory.swap_id == swap.swap_id,
                SwapApprovalHistory.to_status == SwapStatus.APPROVED,
            )
        ).scalars().first()
        if approved is None:
            issues.append(
                _draft(
                    IssueType.UNAPPROVED_SWAP,
                    f"Swap {swap.swap_id} was applied without a recorded manager approval.",
                    employee_id=swap.requester_employee_id,
                    transaction_type="SWAP",
                    transaction_id=swap.swap_id,
                )
            )
    return issues


def _detect_rest_and_hours(db: Session, start, end) -> list[dict]:
    rows = _active_assignment_rows(db, start, end)
    issues: list[dict] = []
    employees = {
        e.employee_id: e
        for e in db.execute(select(Employee)).scalars()
    }
    by_employee: dict[str, list] = {}
    for row in rows:
        by_employee.setdefault(row.employee_id, []).append(row)
    for employee_id, assignments in by_employee.items():
        employee = employees.get(employee_id)
        min_rest = employee.min_rest_hours if employee else 11.0
        ordered = sorted(assignments, key=lambda r: r.start_at)
        for first, second in zip(ordered, ordered[1:]):
            if overlaps(first.start_at, first.end_at, second.start_at, second.end_at):
                continue  # double-booking is reported by its own rule
            gap = rest_gap_hours(first.end_at, second.start_at)
            if 0 <= gap < min_rest:
                issues.append(
                    _draft(
                        IssueType.REST_VIOLATION,
                        f"Employee {employee_id} has only {gap:.1f}h rest between "
                        f"{first.shift_id} and {second.shift_id} (minimum {min_rest:.0f}h).",
                        employee_id=employee_id,
                        shift_id=second.shift_id,
                        assignment_id=second.assignment_id,
                        transaction_type="ASSIGNMENT",
                        transaction_id=first.assignment_id,
                    )
                )
        # Scheduled weekly hours above cap + overtime allowance.
        weeks: dict[date, float] = {}
        for row in assignments:
            weeks[week_start(row.shift_date)] = weeks.get(week_start(row.shift_date), 0.0) + float(
                (row.end_at - row.start_at).total_seconds() / 3600
            )
        for monday, hours in weeks.items():
            cap = (employee.weekly_hours_cap + employee.overtime_cap_weekly) if employee else 50.0
            if hours > cap + 0.01:
                issues.append(
                    _draft(
                        IssueType.HOURS_CAP,
                        f"Employee {employee_id} is scheduled {hours:.1f}h in week {monday}, "
                        f"above the {cap:.0f}h limit.",
                        employee_id=employee_id,
                        transaction_type="WEEK",
                        transaction_id=str(monday),
                    )
                )
    return issues


def _detect_attendance_mismatch(db: Session, start, end) -> list[dict]:
    stmt = (
        select(AttendanceEvent)
        .where(
            func.date(AttendanceEvent.scheduled_start) >= start,
            func.date(AttendanceEvent.scheduled_start) <= end,
        )
    )
    issues = []
    for event in db.execute(stmt).scalars():
        if event.assignment_id is None:
            continue
        assignment = db.get(ShiftAssignment, event.assignment_id)
        if assignment is None:
            issues.append(
                _draft(
                    IssueType.ATTENDANCE_MISMATCH,
                    f"Attendance {event.attendance_id} references a missing assignment.",
                    employee_id=event.employee_id,
                    shift_id=event.shift_id,
                    transaction_type="ATTENDANCE",
                    transaction_id=event.attendance_id,
                )
            )
        elif assignment.employee_id != event.employee_id:
            issues.append(
                _draft(
                    IssueType.ATTENDANCE_MISMATCH,
                    f"Attendance {event.attendance_id} employee does not match assignment "
                    f"{assignment.assignment_id}.",
                    employee_id=event.employee_id,
                    shift_id=event.shift_id,
                    assignment_id=assignment.assignment_id,
                    transaction_type="ATTENDANCE",
                    transaction_id=event.attendance_id,
                )
            )
    return issues


def detect_issues(
    db: Session,
    *,
    start: date | None = None,
    end: date | None = None,
    run_id: str | None = None,
    include_attendance: bool = False,
) -> list[dict]:
    if start is None:
        start = db.execute(select(func.min(Shift.shift_date))).scalar_one() or date.today()
    if end is None:
        end = db.execute(select(func.max(Shift.shift_date))).scalar_one() or date.today()
    issues: list[dict] = []
    issues.extend(_detect_double_booking(db, start, end))
    issues.extend(_detect_leave_overlap(db, start, end))
    issues.extend(_detect_coverage_and_skills(db, start, end))
    issues.extend(_detect_overtime(db, start, end))
    issues.extend(_detect_unapproved_swaps(db, start, end))
    issues.extend(_detect_rest_and_hours(db, start, end))
    if include_attendance:
        issues.extend(_detect_attendance_mismatch(db, start, end))
    for issue in issues:
        issue["run_id"] = run_id
    # Deterministic order for reproducible issue IDs / tests.
    issues.sort(key=lambda i: (i["issue_type"].value, i["shift_id"] or "", i["employee_id"] or "",
                               i["transaction_id"] or ""))
    return issues


def persist_issues(db: Session, actor: User | None, drafts: list[dict]) -> dict:
    new_count = 0
    updated_count = 0
    by_type: dict[str, int] = {}
    for draft in drafts:
        by_type[draft["issue_type"].value] = by_type.get(draft["issue_type"].value, 0) + 1
        existing = db.execute(
            select(SchedulingException).where(
                SchedulingException.fingerprint == draft["fingerprint"]
            )
        ).scalar_one_or_none()
        if existing:
            if existing.resolution_status == ResolutionStatus.OPEN:
                existing.detected_at = utcnow()
                existing.description = draft["description"]
                updated_count += 1
            continue
        issue = SchedulingException(
            issue_id=next_id(db, "issue", "ISS", 6, year=date.today().year),
            run_id=draft.get("run_id"),
            issue_type=draft["issue_type"],
            employee_id=draft.get("employee_id"),
            shift_id=draft.get("shift_id"),
            assignment_id=draft.get("assignment_id"),
            transaction_type=draft.get("transaction_type"),
            transaction_id=draft.get("transaction_id"),
            severity=draft["severity"],
            description=draft["description"],
            detection_source="RUNTIME",
            resolution_status=ResolutionStatus.OPEN,
            detected_at=utcnow(),
            fingerprint=draft["fingerprint"],
        )
        db.add(issue)
        new_count += 1
    if actor:
        record_audit(
            db, actor, "RUN_EXCEPTION_DETECTION", "SchedulingException", None,
            new={"detected": len(drafts), "new": new_count, "by_type": by_type},
        )
    db.commit()
    return {
        "detected": len(drafts),
        "new": new_count,
        "updated": updated_count,
        "by_type": by_type,
    }


def list_exceptions(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 25,
    issue_type: IssueType | None = None,
    status: ResolutionStatus | None = None,
    severity: Severity | None = None,
    run_id: str | None = None,
) -> tuple[list[SchedulingException], int]:
    from app.api.deps import managed_team_ids

    stmt = select(SchedulingException).options(
        # relationships are loaded lazily by the response schema properties
    )
    role = user.role_value
    if role == RoleName.MANAGER:
        teams = managed_team_ids(db, user)
        stmt = stmt.join(
            Employee, Employee.employee_id == SchedulingException.employee_id
        ).where(Employee.team_id.in_(teams or ["__none__"]))
    elif role == RoleName.EMPLOYEE:
        stmt = stmt.where(SchedulingException.employee_id == (user.employee_id or "__none__"))
    if issue_type:
        stmt = stmt.where(SchedulingException.issue_type == issue_type)
    if status:
        stmt = stmt.where(SchedulingException.resolution_status == status)
    if severity:
        stmt = stmt.where(SchedulingException.severity == severity)
    if run_id:
        stmt = stmt.where(SchedulingException.run_id == run_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(SchedulingException.detected_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().scalars()
    )
    return rows, total


def get_exception(db: Session, issue_id: str) -> SchedulingException:
    row = db.get(SchedulingException, issue_id)
    if row is None:
        raise NotFoundError("Exception not found")
    return row


def resolve_exception(db: Session, actor: User, issue_id: str, status: ResolutionStatus,
                      note: str | None) -> SchedulingException:
    issue = get_exception(db, issue_id)
    previous = issue.resolution_status
    issue.resolution_status = status
    issue.resolution_note = note
    issue.resolved_by_user_id = actor.user_id
    issue.resolved_at = utcnow()
    record_audit(db, actor, "RESOLVE_EXCEPTION", "SchedulingException", issue_id,
                 previous={"status": previous.value}, new={"status": status.value,
                                                            "note": note})
    db.commit()
    db.refresh(issue)
    return issue
