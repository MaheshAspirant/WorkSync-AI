"""Database and business-rule integrity checks exposed to administrators."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.master import Employee, Shift


def _scalar(db: Session, sql: str, **params) -> int:
    return int(db.execute(text(sql), params).scalar_one())


def run_validation(db: Session) -> dict:
    checks: list[dict] = []

    def add(name: str, count: int, detail: str, *, fail_at: int = 1):
        status = "PASS" if count < fail_at else "FAIL"
        checks.append({"name": name, "status": status, "detail": detail, "count": count})

    # Primary-key / natural-key uniqueness.
    add(
        "employee_email_uniqueness",
        _scalar(db, "SELECT COUNT(*) FROM (SELECT email FROM employees GROUP BY email HAVING COUNT(*) > 1) x"),
        "Duplicate employee emails",
    )
    add(
        "assignment_uniqueness",
        _scalar(
            db,
            "SELECT COUNT(*) FROM (SELECT shift_id, employee_id FROM shift_assignments "
            "WHERE status IN ('SCHEDULED','CONFIRMED','COMPLETED','SWAPPED_IN') "
            "GROUP BY shift_id, employee_id HAVING COUNT(*) > 1) x",
        ),
        "Duplicate active (shift, employee) assignments",
    )
    add(
        "team_name_uniqueness",
        _scalar(db, "SELECT COUNT(*) FROM (SELECT name FROM teams GROUP BY name HAVING COUNT(*) > 1) x"),
        "Duplicate team names",
    )

    # Foreign-key integrity (explicit orphan checks).
    fk_checks = [
        ("employees_team_fk", "SELECT COUNT(*) FROM employees e LEFT JOIN teams t ON t.team_id=e.team_id WHERE t.team_id IS NULL"),
        ("shifts_team_fk", "SELECT COUNT(*) FROM shifts s LEFT JOIN teams t ON t.team_id=s.team_id WHERE t.team_id IS NULL"),
        ("shifts_template_fk", "SELECT COUNT(*) FROM shifts s LEFT JOIN shift_templates t ON t.shift_template_id=s.shift_template_id WHERE t.shift_template_id IS NULL"),
        ("assignments_shift_fk", "SELECT COUNT(*) FROM shift_assignments a LEFT JOIN shifts s ON s.shift_id=a.shift_id WHERE s.shift_id IS NULL"),
        ("assignments_employee_fk", "SELECT COUNT(*) FROM shift_assignments a LEFT JOIN employees e ON e.employee_id=a.employee_id WHERE e.employee_id IS NULL"),
        ("leaves_employee_fk", "SELECT COUNT(*) FROM leave_requests l LEFT JOIN employees e ON e.employee_id=l.employee_id WHERE e.employee_id IS NULL"),
        ("attendance_assignment_fk", "SELECT COUNT(*) FROM attendance_events a LEFT JOIN shift_assignments s ON s.assignment_id=a.assignment_id WHERE a.assignment_id IS NOT NULL AND s.assignment_id IS NULL"),
        ("swap_assignments_fk", "SELECT COUNT(*) FROM swap_requests s LEFT JOIN shift_assignments a ON a.assignment_id=s.requester_assignment_id WHERE a.assignment_id IS NULL"),
    ]
    for name, sql in fk_checks:
        add(name, _scalar(db, sql), f"Orphan rows for {name}")

    # Enum / lifecycle checks.
    add(
        "leave_history_exists",
        _scalar(db, "SELECT COUNT(*) FROM leave_requests l WHERE NOT EXISTS (SELECT 1 FROM leave_approval_history h WHERE h.leave_id=l.leave_id)"),
        "Leave requests without lifecycle history",
    )
    unapproved_swaps = _scalar(
        db,
        "SELECT COUNT(*) FROM swap_requests s WHERE s.status='APPLIED' AND NOT EXISTS "
        "(SELECT 1 FROM swap_approval_history h WHERE h.swap_id=s.swap_id AND h.to_status='APPROVED')",
    )
    checks.append(
        {
            "name": "applied_swaps_without_approval",
            "status": "WARN" if unapproved_swaps else "PASS",
            "detail": (
                "Labelled unapproved-swap anomaly present; reported as an exception for review"
                if unapproved_swaps else "All applied swaps have an approval event"
            ),
            "count": unapproved_swaps,
        }
    )
    add(
        "leave_date_order",
        _scalar(db, "SELECT COUNT(*) FROM leave_requests WHERE end_date < start_date"),
        "Leave requests with end before start",
    )
    add(
        "shift_date_order",
        _scalar(db, "SELECT COUNT(*) FROM shifts WHERE end_at <= start_at"),
        "Shifts with end at or before start",
    )

    # Working-hour constraint from active assignments (dialect-neutral aggregation).
    from app.core.workforce import week_start

    caps = {
        employee_id: (cap, ot_cap)
        for employee_id, cap, ot_cap in db.execute(
            text("SELECT employee_id, weekly_hours_cap, overtime_cap_weekly FROM employees")
        ).all()
    }
    weekly: dict[tuple[str, date], float] = {}
    for employee_id, shift_date, hours in db.execute(
        text(
            """
            SELECT a.employee_id, s.shift_date, a.scheduled_hours
            FROM shift_assignments a
            JOIN shifts s ON s.shift_id = a.shift_id
            WHERE a.status IN ('SCHEDULED','CONFIRMED','COMPLETED','SWAPPED_IN')
            """
        )
    ).all():
        if isinstance(shift_date, str):
            shift_date = date.fromisoformat(shift_date)
        monday = week_start(shift_date)
        weekly[(employee_id, monday)] = weekly.get((employee_id, monday), 0.0) + float(hours)
    over_hours = sum(
        1
        for (employee_id, _monday), hours in weekly.items()
        if hours > caps.get(employee_id, (40.0, 10.0))[0] + caps.get(employee_id, (40.0, 10.0))[1] + 0.01
    )
    add("weekly_hours_cap", int(over_hours), "Employee-weeks above cap + overtime allowance")

    # Coverage: shifts below required headcount.
    coverage_gaps = _scalar(
        db,
        """
        SELECT COUNT(*) FROM shifts s
        WHERE s.shift_date <= :today
          AND (SELECT COUNT(*) FROM shift_assignments a
               WHERE a.shift_id=s.shift_id
                 AND a.status IN ('SCHEDULED','CONFIRMED','COMPLETED','SWAPPED_IN')) < s.required_staff
        """,
        today=date.today().isoformat(),
    )
    checks.append(
        {
            "name": "coverage_gaps",
            "status": "WARN" if coverage_gaps else "PASS",
            "detail": "Historical/target shifts below required staffing (reported as exceptions)",
            "count": coverage_gaps,
        }
    )

    failures = sum(1 for c in checks if c["status"] == "FAIL")
    status = "PASS" if failures == 0 else "FAIL"
    return {"checked_at": utcnow(), "status": status, "checks": checks, "failures": failures}
