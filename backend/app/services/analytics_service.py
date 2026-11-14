"""Analytics calculated from persisted operational data.

Every metric is derived from database records; nothing in this module is a
hard-coded dashboard value.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.workforce import classify_day, week_start
from app.models.attendance import AttendanceEvent
from app.models.audit import AuditLog
from app.models.enums import (
    AssignmentStatus,
    AttendanceStatus,
    DayType,
    IssueType,
    LeaveStatus,
    ResolutionStatus,
    ShiftStatus,
)
from app.models.leave import LeaveRequest
from app.models.master import Employee, EmployeeSkill, HolidayCalendar, Shift, Team
from app.models.scheduling import (
    CoverageRequirement,
    SchedulingException,
    ShiftAssignment,
)
from app.services.attendance_service import weekly_overtime_rows

ACTIVE_STATUSES = [
    AssignmentStatus.SCHEDULED,
    AssignmentStatus.CONFIRMED,
    AssignmentStatus.COMPLETED,
    AssignmentStatus.SWAPPED_IN,
]


def default_period(db: Session, start: date | None, end: date | None) -> tuple[date, date]:
    if start and end:
        return start, end
    max_day = db.execute(select(func.max(Shift.shift_date))).scalar_one()
    min_day = db.execute(select(func.min(Shift.shift_date))).scalar_one()
    if max_day is None:
        today = date.today()
        return start or today - timedelta(days=29), end or today
    if end is None:
        # Prefer the current date when it falls inside the dataset window so
        # dashboards show the live period rather than a future-only window.
        today = date.today()
        end = today if min_day <= today <= max_day else max_day
    start = start or max(min_day, end - timedelta(days=29))
    return start, end


def _coverage_data(db: Session, start: date, end: date) -> dict:
    shifts = db.execute(
        select(
            Shift.shift_id,
            Shift.team_id,
            Shift.shift_template_id,
            Shift.shift_date,
            Shift.required_staff,
        ).where(Shift.shift_date >= start, Shift.shift_date <= end)
    ).all()
    assignments = db.execute(
        select(
            ShiftAssignment.shift_id,
            ShiftAssignment.employee_id,
            ShiftAssignment.assignment_id,
        ).where(ShiftAssignment.status.in_(ACTIVE_STATUSES))
    ).all()
    by_shift: dict[str, list[tuple[str, str]]] = {}
    for shift_id, employee_id, assignment_id in assignments:
        by_shift.setdefault(shift_id, []).append((employee_id, assignment_id))
    reqs = db.execute(
        select(CoverageRequirement).where(
            CoverageRequirement.effective_from <= end,
            (CoverageRequirement.effective_to.is_(None))
            | (CoverageRequirement.effective_to >= start),
        )
    ).scalars().all()
    req_by_key: dict[tuple, list[CoverageRequirement]] = {}
    for req in reqs:
        req_by_key.setdefault((req.team_id, req.shift_template_id), []).append(req)
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
    teams = {t.team_id: t.name for t in db.execute(select(Team)).scalars()}

    required_positions = 0
    filled_positions = 0
    skill_required = 0
    skill_filled = 0
    by_team: dict[str, dict] = {}
    by_day: dict[date, dict] = {}
    gaps = []
    for shift in shifts:
        assigned_rows = by_shift.get(shift.shift_id, [])
        assigned = len(assigned_rows)
        required = shift.required_staff
        required_positions += required
        filled_positions += min(assigned, required)
        team_bucket = by_team.setdefault(
            shift.team_id,
            {"team_id": shift.team_id, "team_name": teams.get(shift.team_id, shift.team_id),
             "required": 0, "filled": 0, "shifts": 0},
        )
        team_bucket["required"] += required
        team_bucket["filled"] += min(assigned, required)
        team_bucket["shifts"] += 1
        day_bucket = by_day.setdefault(
            shift.shift_date, {"date": shift.shift_date, "required": 0, "filled": 0}
        )
        day_bucket["required"] += required
        day_bucket["filled"] += min(assigned, required)
        if assigned < required:
            gaps.append(
                {
                    "shift_id": shift.shift_id,
                    "team_id": shift.team_id,
                    "team_name": teams.get(shift.team_id, shift.team_id),
                    "shift_date": shift.shift_date,
                    "required": required,
                    "assigned": assigned,
                    "gap": required - assigned,
                }
            )
        day_type = classify_day(shift.shift_date, holidays)
        for req in req_by_key.get((shift.team_id, shift.shift_template_id), []):
            if not req.skill_id:
                continue
            if req.day_type not in {DayType.ALL, day_type}:
                continue
            if req.effective_from > shift.shift_date:
                continue
            if req.effective_to and req.effective_to < shift.shift_date:
                continue
            qualified = sum(
                1 for employee_id, _ in assigned_rows
                if req.skill_id in skills_by_employee.get(employee_id, set())
            )
            skill_required += req.min_staff
            skill_filled += min(qualified, req.min_staff)

    for bucket in by_team.values():
        bucket["coverage_pct"] = round(
            bucket["filled"] / bucket["required"] * 100, 2
        ) if bucket["required"] else 100.0
    for bucket in by_day.values():
        bucket["coverage_pct"] = round(
            bucket["filled"] / bucket["required"] * 100, 2
        ) if bucket["required"] else 100.0
    gaps.sort(key=lambda g: (g["gap"], g["shift_date"]), reverse=True)
    return {
        "required_positions": required_positions,
        "filled_positions": filled_positions,
        "coverage_pct": round(filled_positions / required_positions * 100, 2)
        if required_positions else 100.0,
        "skill_required_positions": skill_required,
        "skill_filled_positions": skill_filled,
        "skill_coverage_pct": round(skill_filled / skill_required * 100, 2)
        if skill_required else 100.0,
        "by_team": sorted(by_team.values(), key=lambda b: b["team_name"]),
        "by_day": [by_day[d] for d in sorted(by_day)],
        "top_gaps": gaps[:10],
    }


def _overtime_data(db: Session, start: date, end: date) -> dict:
    rows = weekly_overtime_rows(db, start=start, end=end)
    total = round(sum(r["overtime_hours"] for r in rows), 2)
    employees = {r["employee_id"] for r in rows}
    over_cap = {r["employee_id"] for r in rows if r["cap_exceeded"]}
    by_week: dict[date, float] = {}
    by_team: dict[str, float] = {}
    top = sorted(rows, key=lambda r: r["overtime_hours"], reverse=True)[:10]
    for row in rows:
        by_week[row["week_start"]] = round(
            by_week.get(row["week_start"], 0.0) + row["overtime_hours"], 2
        )
        by_team[row["team_id"]] = round(by_team.get(row["team_id"], 0.0) + row["overtime_hours"], 2)
    teams = {t.team_id: t.name for t in db.execute(select(Team)).scalars()}
    return {
        "total_overtime_hours": total,
        "average_overtime_per_employee": round(total / len(employees), 2) if employees else 0.0,
        "employees_over_cap": len(over_cap),
        "by_week": [{"week_start": k, "overtime_hours": v} for k, v in sorted(by_week.items())],
        "by_team": [{"team_id": k, "team_name": teams.get(k, k), "overtime_hours": v}
                    for k, v in sorted(by_team.items(), key=lambda x: -x[1])],
        "top_employees": [
            {
                "employee_id": r["employee_id"],
                "employee_name": r["employee_name"],
                "team_id": r["team_id"],
                "week_start": r["week_start"],
                "overtime_hours": r["overtime_hours"],
                "overtime_cap": r["overtime_cap"],
                "cap_exceeded": r["cap_exceeded"],
            }
            for r in top
        ],
        "_rows": rows,
    }


def _fairness_data(db: Session, start: date, end: date, overtime_rows: list[dict]) -> dict:
    rows = db.execute(
        select(
            ShiftAssignment.employee_id,
            Employee.first_name,
            Employee.last_name,
            Employee.team_id,
            Shift.shift_date,
            Shift.start_at,
            Shift.end_at,
            Shift.shift_template_id,
        )
        .join(Employee, Employee.employee_id == ShiftAssignment.employee_id)
        .join(Shift, Shift.shift_id == ShiftAssignment.shift_id)
        .where(
            ShiftAssignment.status.in_(ACTIVE_STATUSES),
            Shift.shift_date >= start,
            Shift.shift_date <= end,
        )
    ).all()
    from app.models.master import ShiftTemplate

    template_codes = {
        t.shift_template_id: t.code
        for t in db.execute(select(ShiftTemplate)).scalars()
    }
    by_employee: dict[str, dict] = {}
    for row in rows:
        bucket = by_employee.setdefault(
            row.employee_id,
            {
                "employee_id": row.employee_id,
                "employee_name": f"{row.first_name} {row.last_name}",
                "team_id": row.team_id,
                "morning": 0,
                "evening": 0,
                "night": 0,
                "weekend": 0,
                "total_shifts": 0,
                "overtime_hours": 0.0,
            },
        )
        code = template_codes.get(row.shift_template_id, "A")
        bucket["total_shifts"] += 1
        if code == "A":
            bucket["morning"] += 1
        elif code == "B":
            bucket["evening"] += 1
        elif code == "C":
            bucket["night"] += 1
        if row.shift_date.weekday() >= 5:
            bucket["weekend"] += 1
    for row in overtime_rows:
        bucket = by_employee.get(row["employee_id"])
        if bucket:
            bucket["overtime_hours"] = round(bucket["overtime_hours"] + row["overtime_hours"], 2)

    def normalized_score(values: list[float]) -> float:
        if not values:
            return 1.0
        mean = statistics.mean(values)
        if mean <= 0:
            return 1.0
        cv = statistics.pstdev(values) / mean
        return max(0.0, min(1.0, 1.0 - cv))

    night_values = [b["night"] for b in by_employee.values()]
    weekend_values = [b["weekend"] for b in by_employee.values()]
    overtime_values = [b["overtime_hours"] for b in by_employee.values()]
    night_score = normalized_score(night_values)
    weekend_score = normalized_score(weekend_values)
    overtime_score = normalized_score(overtime_values)
    fairness = round((night_score + weekend_score + overtime_score) / 3 * 100, 2)
    ordered = sorted(
        by_employee.values(),
        key=lambda b: (b["night"], b["overtime_hours"], b["employee_id"]),
        reverse=True,
    )
    return {
        "fairness_score": fairness,
        "night_shift_score": round(night_score * 100, 2),
        "weekend_shift_score": round(weekend_score * 100, 2),
        "overtime_score": round(overtime_score * 100, 2),
        "by_employee": ordered,
        "explanation": (
            "Fairness is the mean of three normalised distribution scores "
            "(night shifts, weekend shifts, overtime). Each score is max(0, 1 - coefficient of "
            "variation) across employees with assignments, so an even distribution scores 100 "
            "and a highly concentrated one approaches 0."
        ),
    }


def dashboard(db: Session, start: date | None = None, end: date | None = None) -> dict:
    start, end = default_period(db, start, end)
    total_employees = db.execute(select(func.count()).select_from(Employee)).scalar_one()
    active_employees = db.execute(
        select(func.count()).select_from(Employee).where(Employee.status == "ACTIVE")
    ).scalar_one()
    total_teams = db.execute(select(func.count()).select_from(Team)).scalar_one()
    total_shifts = db.execute(
        select(func.count()).select_from(Shift).where(
            Shift.shift_date >= start, Shift.shift_date <= end
        )
    ).scalar_one()
    total_assignments = db.execute(
        select(func.count()).select_from(ShiftAssignment).where(
            ShiftAssignment.status.in_(ACTIVE_STATUSES)
        )
    ).scalar_one()
    leave_counts = dict(
        db.execute(select(LeaveRequest.status, func.count()).group_by(LeaveRequest.status)).all()
    )
    total_leaves = sum(leave_counts.values())
    coverage = _coverage_data(db, start, end)
    overtime = _overtime_data(db, start, end)
    absence_counts = dict(
        db.execute(
            select(AttendanceEvent.status, func.count())
            .where(
                func.date(AttendanceEvent.scheduled_start) >= start,
                func.date(AttendanceEvent.scheduled_start) <= end,
            )
            .group_by(AttendanceEvent.status)
        ).all()
    )
    total_attendance = sum(absence_counts.values())
    absent = sum(
        count for status, count in absence_counts.items()
        if status in {AttendanceStatus.ABSENT, AttendanceStatus.NO_SHOW}
    )
    open_exceptions = db.execute(
        select(func.count()).select_from(SchedulingException).where(
            SchedulingException.resolution_status == ResolutionStatus.OPEN
        )
    ).scalar_one()
    total_exceptions = db.execute(
        select(func.count()).select_from(SchedulingException)
    ).scalar_one()
    affected_assignments = db.execute(
        select(func.count(func.distinct(SchedulingException.assignment_id))).where(
            SchedulingException.assignment_id.is_not(None),
            SchedulingException.resolution_status == ResolutionStatus.OPEN,
        )
    ).scalar_one()
    period_assignments = db.execute(
        select(func.count()).select_from(ShiftAssignment)
        .join(Shift, Shift.shift_id == ShiftAssignment.shift_id)
        .where(
            ShiftAssignment.status.in_(ACTIVE_STATUSES),
            Shift.shift_date >= start,
            Shift.shift_date <= end,
        )
    ).scalar_one()
    validity = round(
        (period_assignments - min(affected_assignments, period_assignments)) / period_assignments * 100,
        2,
    ) if period_assignments else 100.0
    fairness = _fairness_data(db, start, end, overtime["_rows"])
    return {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "total_teams": total_teams,
        "total_shifts": total_shifts,
        "total_assignments": total_assignments,
        "total_leave_requests": total_leaves,
        "approved_leave_requests": leave_counts.get(LeaveStatus.APPROVED, 0),
        "pending_leave_requests": leave_counts.get(LeaveStatus.PENDING, 0),
        "rejected_leave_requests": leave_counts.get(LeaveStatus.REJECTED, 0),
        "coverage_pct": coverage["coverage_pct"],
        "skill_coverage_pct": coverage["skill_coverage_pct"],
        "total_overtime_hours": overtime["total_overtime_hours"],
        "avg_overtime_per_employee": overtime["average_overtime_per_employee"],
        "absence_rate": round(absent / total_attendance * 100, 2) if total_attendance else 0.0,
        "conflict_count": total_exceptions,
        "open_conflict_count": open_exceptions,
        "fairness_score": fairness["fairness_score"],
        "schedule_validity_pct": validity,
        "period_start": start,
        "period_end": end,
    }


def coverage_analytics(db: Session, start: date | None, end: date | None) -> dict:
    start, end = default_period(db, start, end)
    data = _coverage_data(db, start, end)
    return {
        "period_start": start,
        "period_end": end,
        **{k: data[k] for k in (
            "required_positions", "filled_positions", "coverage_pct",
            "skill_required_positions", "skill_filled_positions", "skill_coverage_pct",
            "by_team", "by_day", "top_gaps",
        )},
    }


def overtime_analytics(db: Session, start: date | None, end: date | None) -> dict:
    start, end = default_period(db, start, end)
    data = _overtime_data(db, start, end)
    data.pop("_rows", None)
    return {"period_start": start, "period_end": end, **data}


def fairness_analytics(db: Session, start: date | None, end: date | None) -> dict:
    start, end = default_period(db, start, end)
    overtime = _overtime_data(db, start, end)
    data = _fairness_data(db, start, end, overtime["_rows"])
    return {"period_start": start, "period_end": end, **data}


def leave_analytics(db: Session, start: date | None, end: date | None) -> dict:
    start, end = default_period(db, start, end)
    by_status = [
        {"status": status.value, "count": count}
        for status, count in db.execute(
            select(LeaveRequest.status, func.count()).group_by(LeaveRequest.status)
        ).all()
    ]
    by_type = [
        {"leave_type": leave_type.value, "count": count}
        for leave_type, count in db.execute(
            select(LeaveRequest.leave_type, func.count()).group_by(LeaveRequest.leave_type)
        ).all()
    ]
    by_month_rows = db.execute(
        select(
            func.strftime("%Y-%m", LeaveRequest.start_date) if db.bind.dialect.name == "sqlite"
            else func.to_char(LeaveRequest.start_date, "YYYY-MM"),
            func.count(),
        ).group_by(
            func.strftime("%Y-%m", LeaveRequest.start_date) if db.bind.dialect.name == "sqlite"
            else func.to_char(LeaveRequest.start_date, "YYYY-MM")
        )
    ).all()
    approved = next((x["count"] for x in by_status if x["status"] == "APPROVED"), 0)
    rejected = next((x["count"] for x in by_status if x["status"] == "REJECTED"), 0)
    decided = approved + rejected
    return {
        "period_start": start,
        "period_end": end,
        "by_status": by_status,
        "by_type": by_type,
        "by_month": [{"month": month, "count": count} for month, count in by_month_rows],
        "approval_rate": round(approved / decided * 100, 2) if decided else 0.0,
    }


def trends(db: Session, start: date | None, end: date | None) -> dict:
    start, end = default_period(db, start, end)
    shifts = db.execute(
        select(
            Shift.shift_id, Shift.shift_date, Shift.required_staff,
        ).where(Shift.shift_date >= start, Shift.shift_date <= end)
    ).all()
    assigned = dict(
        db.execute(
            select(ShiftAssignment.shift_id, func.count())
            .where(ShiftAssignment.status.in_(ACTIVE_STATUSES))
            .group_by(ShiftAssignment.shift_id)
        ).all()
    )
    coverage_by_week: dict[date, dict] = {}
    for shift in shifts:
        monday = week_start(shift.shift_date)
        bucket = coverage_by_week.setdefault(
            monday, {"week_start": monday, "required": 0, "filled": 0}
        )
        bucket["required"] += shift.required_staff
        bucket["filled"] += min(assigned.get(shift.shift_id, 0), shift.required_staff)
    for bucket in coverage_by_week.values():
        bucket["coverage_pct"] = round(
            bucket["filled"] / bucket["required"] * 100, 2
        ) if bucket["required"] else 100.0
    overtime = _overtime_data(db, start, end)
    absence_rows = db.execute(
        select(
            func.date(AttendanceEvent.scheduled_start) if db.bind.dialect.name == "sqlite"
            else func.date(AttendanceEvent.scheduled_start),
            AttendanceEvent.status,
        ).where(
            func.date(AttendanceEvent.scheduled_start) >= start,
            func.date(AttendanceEvent.scheduled_start) <= end,
        )
    ).all()
    absence_by_week: dict[date, dict] = {}
    for day, status in absence_rows:
        if isinstance(day, str):
            day = date.fromisoformat(day)
        monday = week_start(day)
        bucket = absence_by_week.setdefault(
            monday, {"week_start": monday, "total": 0, "absent": 0}
        )
        bucket["total"] += 1
        if status in {AttendanceStatus.ABSENT, AttendanceStatus.NO_SHOW}:
            bucket["absent"] += 1
    for bucket in absence_by_week.values():
        bucket["absence_rate"] = round(
            bucket["absent"] / bucket["total"] * 100, 2
        ) if bucket["total"] else 0.0
    return {
        "period_start": start,
        "period_end": end,
        "coverage": [coverage_by_week[k] for k in sorted(coverage_by_week)],
        "overtime": overtime["by_week"],
        "absences": [absence_by_week[k] for k in sorted(absence_by_week)],
    }
