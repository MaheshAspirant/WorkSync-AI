"""Dataset validation for generated CSV/DB records.

Two phases are validated:
1. the baseline dataset must satisfy uniqueness, referential integrity,
   lifecycle, arithmetic, working-hour and rest rules;
2. the injected anomalies are verified to be present and labelled in ground
   truth (they intentionally violate those same rules).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

ACTIVE = {"SCHEDULED", "CONFIRMED", "COMPLETED", "SWAPPED_IN"}

PRIMARY_KEYS = {
    "teams": ["team_id"],
    "skills": ["skill_id"],
    "employees": ["employee_id"],
    "employee_skills": ["employee_id", "skill_id"],
    "employee_availability": ["availability_id"],
    "team_managers": ["team_manager_id"],
    "shift_templates": ["shift_template_id"],
    "coverage_requirements": ["coverage_id"],
    "holiday_calendar": ["holiday_id"],
    "leave_policies": ["policy_id"],
    "leave_requests": ["leave_id"],
    "leave_approval_history": ["history_id"],
    "shifts": ["shift_id"],
    "shift_assignments": ["assignment_id"],
    "attendance_events": ["attendance_id"],
    "swap_requests": ["swap_id"],
    "swap_approval_history": ["history_id"],
}

FK_PAIRS = [
    ("employees", "team_id", "teams", "team_id", False),
    ("employee_skills", "employee_id", "employees", "employee_id", False),
    ("employee_skills", "skill_id", "skills", "skill_id", False),
    ("employee_availability", "employee_id", "employees", "employee_id", False),
    ("team_managers", "team_id", "teams", "team_id", False),
    ("team_managers", "employee_id", "employees", "employee_id", False),
    ("coverage_requirements", "team_id", "teams", "team_id", False),
    ("coverage_requirements", "shift_template_id", "shift_templates", "shift_template_id", False),
    ("coverage_requirements", "skill_id", "skills", "skill_id", True),
    ("leave_requests", "employee_id", "employees", "employee_id", False),
    ("leave_requests", "policy_id", "leave_policies", "policy_id", False),
    ("leave_approval_history", "leave_id", "leave_requests", "leave_id", False),
    ("shifts", "team_id", "teams", "team_id", False),
    ("shifts", "shift_template_id", "shift_templates", "shift_template_id", False),
    ("shift_assignments", "shift_id", "shifts", "shift_id", False),
    ("shift_assignments", "employee_id", "employees", "employee_id", False),
    ("attendance_events", "employee_id", "employees", "employee_id", False),
    ("attendance_events", "shift_id", "shifts", "shift_id", True),
    ("attendance_events", "assignment_id", "shift_assignments", "assignment_id", True),
    ("swap_requests", "requester_employee_id", "employees", "employee_id", False),
    ("swap_requests", "target_employee_id", "employees", "employee_id", False),
    ("swap_requests", "requester_assignment_id", "shift_assignments", "assignment_id", False),
    ("swap_requests", "target_assignment_id", "shift_assignments", "assignment_id", False),
    ("swap_approval_history", "swap_id", "swap_requests", "swap_id", False),
]

ENUMS = {
    "employees": {"status": {"ACTIVE", "ON_LEAVE", "INACTIVE", "TERMINATED"},
                  "employment_type": {"FULL_TIME", "PART_TIME", "CONTRACT", "INTERN"},
                  "preferred_shift": {"MORNING", "EVENING", "NIGHT", "NONE"}},
    "shifts": {"status": {"PLANNED", "PUBLISHED", "COMPLETED", "CANCELLED"}},
    "shift_assignments": {"status": {"SCHEDULED", "CONFIRMED", "COMPLETED", "CANCELLED",
                                      "SWAPPED_OUT", "SWAPPED_IN", "NO_SHOW"},
                           "assignment_source": {"BASELINE", "OPTIMIZER", "MANUAL", "SWAP"}},
    "leave_requests": {"leave_type": {"ANNUAL", "SICK", "UNPAID", "PARENTAL", "BEREAVEMENT"},
                        "status": {"PENDING", "APPROVED", "REJECTED", "CANCELLED"}},
    "attendance_events": {"status": {"PRESENT", "LATE", "ABSENT", "EARLY_DEPARTURE",
                                      "NO_SHOW", "ON_LEAVE"},
                           "source": {"BIOMETRIC", "MANUAL", "MOBILE"},
                           "reconciliation_status": {"MATCHED", "MISMATCH", "PENDING"}},
    "swap_requests": {"status": {"REQUESTED", "APPROVED", "REJECTED", "CANCELLED", "APPLIED"}},
    "coverage_requirements": {"day_type": {"ALL", "WEEKDAY", "WEEKEND", "HOLIDAY"}},
}


def _check(checks: list[dict], name: str, count: int, detail: str, *, fail_at: int = 1,
           warn: bool = False):
    if count < fail_at:
        status = "PASS"
    elif warn:
        status = "WARN"
    else:
        status = "FAIL"
    checks.append({"name": name, "status": status, "detail": detail, "count": count})


def validate_dataset(data: dict[str, list[dict]], *, mode: str = "baseline",
                     ground_truth: list[dict] | None = None) -> dict:
    checks: list[dict] = []
    ground_truth = ground_truth or []

    # Primary-key and natural-key uniqueness.
    for table, keys in PRIMARY_KEYS.items():
        rows = data.get(table, [])
        seen = set()
        duplicates = 0
        for row in rows:
            key = tuple(row.get(k) for k in keys)
            if key in seen:
                duplicates += 1
            seen.add(key)
        _check(checks, f"pk_unique:{table}", duplicates, f"Duplicate primary key rows in {table}")

    seen = set()
    duplicate_assignments = 0
    for row in data.get("shift_assignments", []):
        key = (row["shift_id"], row["employee_id"])
        if key in seen:
            duplicate_assignments += 1
        seen.add(key)
    _check(checks, "assignment_shift_employee_unique", duplicate_assignments,
           "Duplicate (shift, employee) assignments")

    emails = [r["email"] for r in data.get("employees", [])]
    _check(checks, "employee_email_unique", len(emails) - len(set(emails)),
           "Duplicate employee emails")

    # Foreign-key integrity.
    indexes = {
        table: {tuple(row.get(k) for k in keys) for row in data.get(table, [])}
        for table, keys in PRIMARY_KEYS.items()
    }
    for table, column, parent, parent_column, nullable in FK_PAIRS:
        parent_index = {key[0] for key in indexes.get(parent, set())}
        missing = 0
        for row in data.get(table, []):
            value = row.get(column)
            if value is None and nullable:
                continue
            if value not in parent_index:
                missing += 1
        _check(checks, f"fk:{table}.{column}->{parent}.{parent_column}", missing,
               f"Orphan {table}.{column} references")

    # Enum validity.
    for table, fields in ENUMS.items():
        for field, allowed in fields.items():
            invalid = sum(1 for r in data.get(table, []) if r.get(field) not in allowed)
            _check(checks, f"enum:{table}.{field}", invalid, f"Invalid {field} values in {table}")

    # Dates / arithmetic.
    date_errors = 0
    for leave in data.get("leave_requests", []):
        start = leave.get("start_date")
        end = leave.get("end_date")
        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)
        if not start or not end or end < start:
            date_errors += 1
    _check(checks, "leave_date_order", date_errors, "Leave rows with end_date before start_date")

    shift_errors = 0
    for shift in data.get("shifts", []):
        start = shift.get("start_at")
        end = shift.get("end_at")
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)
        if not start or not end or end <= start:
            shift_errors += 1
    _check(checks, "shift_datetime_order", shift_errors, "Shifts with end <= start")

    holidays = {
        (r["holiday_date"] if isinstance(r["holiday_date"], date) else date.fromisoformat(r["holiday_date"]))
        for r in data.get("holiday_calendar", [])
    }

    def working_days(start: date, end: date) -> int:
        count = 0
        cursor = start
        while cursor <= end:
            if cursor.weekday() < 5 and cursor not in holidays:
                count += 1
            cursor += timedelta(days=1)
        return count

    leave_days_errors = 0
    for leave in data.get("leave_requests", []):
        start = leave["start_date"]
        end = leave["end_date"]
        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)
        expected = working_days(start, end)
        if abs(expected - float(leave["total_days"])) > 0.01:
            leave_days_errors += 1
    _check(checks, "leave_total_days_reconcile", leave_days_errors,
           "Leave total_days does not match working days")

    attendance_errors = 0
    for event in data.get("attendance_events", []):
        check_in = event.get("actual_check_in")
        check_out = event.get("actual_check_out")
        if check_in and check_out:
            actual = round((check_out - check_in).total_seconds() / 3600, 2)
            if abs(actual - float(event["actual_hours"])) > 0.02:
                attendance_errors += 1
            expected_ot = round(max(0.0, actual - 8.0), 2)
            if abs(expected_ot - float(event["overtime_hours"])) > 0.02:
                attendance_errors += 1
        elif float(event["actual_hours"]) != 0:
            attendance_errors += 1
    _check(checks, "attendance_arithmetic", attendance_errors,
           "Attendance hours/overtime do not reconcile with timestamps")

    # Assignment working hours and rest (baseline only; anomalies are intentional).
    if mode == "baseline":
        employees = {e["employee_id"]: e for e in data.get("employees", [])}
        shifts = {s["shift_id"]: s for s in data.get("shifts", [])}
        caps = {
            employee_id: (e["weekly_hours_cap"], e["overtime_cap_weekly"])
            for employee_id, e in employees.items()
        }
        weekly: dict[tuple[str, date], float] = defaultdict(float)
        by_employee: dict[str, list[dict]] = defaultdict(list)
        for assignment in data.get("shift_assignments", []):
            if assignment["status"] not in ACTIVE:
                continue
            shift = shifts[assignment["shift_id"]]
            monday = shift["shift_date"] - timedelta(days=shift["shift_date"].weekday())
            weekly[(assignment["employee_id"], monday)] += float(assignment["scheduled_hours"])
            by_employee[assignment["employee_id"]].append(shift)
        hours_errors = sum(
            1 for (employee_id, _monday), hours in weekly.items()
            if hours > caps.get(employee_id, (40, 10))[0] + caps.get(employee_id, (40, 10))[1] + 0.01
        )
        _check(checks, "weekly_hours_cap", hours_errors,
               "Employee-weeks above weekly cap + overtime allowance")

        rest_errors = 0
        overlap_errors = 0
        for employee_id, employee_shifts in by_employee.items():
            ordered = sorted(employee_shifts, key=lambda s: s["start_at"])
            min_rest = employees[employee_id]["min_rest_hours"]
            for first, second in zip(ordered, ordered[1:]):
                if first["end_at"] > second["start_at"]:
                    overlap_errors += 1
                gap = (second["start_at"] - first["end_at"]).total_seconds() / 3600
                if gap < min_rest:
                    rest_errors += 1
        _check(checks, "assignment_overlap", overlap_errors, "Overlapping active assignments")
        _check(checks, "minimum_rest", rest_errors, "Assignments below minimum rest")

        gaps = 0
        assigned_by_shift: dict[str, int] = defaultdict(int)
        for assignment in data.get("shift_assignments", []):
            if assignment["status"] in ACTIVE:
                assigned_by_shift[assignment["shift_id"]] += 1
        for shift in data.get("shifts", []):
            if assigned_by_shift.get(shift["shift_id"], 0) < shift["required_staff"]:
                gaps += 1
        _check(checks, "baseline_coverage", gaps,
               "Baseline shifts below required staffing", warn=True)

    # Lifecycle consistency.
    leave_ids = {l["leave_id"] for l in data.get("leave_requests", [])}
    histories: dict[str, list[dict]] = defaultdict(list)
    for history in data.get("leave_approval_history", []):
        histories[history["leave_id"]].append(history)
    lifecycle_errors = sum(1 for leave_id in leave_ids if not histories.get(leave_id))
    for leave in data.get("leave_requests", []):
        if leave["status"] in {"APPROVED", "REJECTED", "CANCELLED"}:
            if not any(h["to_status"] == leave["status"] for h in histories.get(leave["leave_id"], [])):
                lifecycle_errors += 1
    _check(checks, "leave_lifecycle", lifecycle_errors, "Leave rows without matching lifecycle events")

    applied_swaps = [s for s in data.get("swap_requests", []) if s["status"] == "APPLIED"]
    swap_histories: dict[str, list[dict]] = defaultdict(list)
    for history in data.get("swap_approval_history", []):
        swap_histories[history["swap_id"]].append(history)
    unapproved = sum(
        1 for swap in applied_swaps
        if not any(h["to_status"] == "APPROVED" for h in swap_histories.get(swap["swap_id"], []))
    )
    _check(checks, "swap_applied_requires_approval", unapproved,
           "APPLIED swaps without APPROVED history")

    # Duplicate attendance per assignment.
    seen_assignments = set()
    duplicate_attendance = 0
    for event in data.get("attendance_events", []):
        assignment_id = event.get("assignment_id")
        if assignment_id in seen_assignments:
            duplicate_attendance += 1
        seen_assignments.add(assignment_id)
    _check(checks, "attendance_one_per_assignment", duplicate_attendance,
           "Multiple attendance rows for one assignment")

    failures = sum(1 for c in checks if c["status"] == "FAIL")
    return {
        "mode": mode,
        "checks": checks,
        "failures": failures,
        "warnings": sum(1 for c in checks if c["status"] == "WARN"),
        "row_counts": {k: len(v) for k, v in data.items()},
        "ground_truth_rows": len(ground_truth),
        "status": "PASS" if failures == 0 else "FAIL",
    }


def validate_anomalies(data: dict[str, list[dict]], ground_truth: list[dict]) -> dict:
    employees = {e["employee_id"]: e for e in data.get("employees", [])}
    shifts = {s["shift_id"]: s for s in data.get("shifts", [])}
    assignments = data.get("shift_assignments", [])
    active = [a for a in assignments if a["status"] in ACTIVE]
    by_shift: dict[str, list[dict]] = defaultdict(list)
    by_employee: dict[str, list[dict]] = defaultdict(list)
    for assignment in active:
        by_shift[assignment["shift_id"]].append(assignment)
        by_employee[assignment["employee_id"]].append(assignment)

    leave_by_employee: dict[str, list[dict]] = defaultdict(list)
    for leave in data.get("leave_requests", []):
        if leave["status"] == "APPROVED":
            leave_by_employee[leave["employee_id"]].append(leave)

    skills = {
        (row["employee_id"], row["skill_id"]) for row in data.get("employee_skills", [])
    }
    coverage = data.get("coverage_requirements", [])
    holidays = {
        (r["holiday_date"] if isinstance(r["holiday_date"], date) else date.fromisoformat(r["holiday_date"]))
        for r in data.get("holiday_calendar", [])
    }
    templates = {t["shift_template_id"]: t for t in data.get("shift_templates", [])}
    attendance = data.get("attendance_events", [])
    swaps = {s["swap_id"]: s for s in data.get("swap_requests", [])}
    swap_histories: dict[str, list[dict]] = defaultdict(list)
    for history in data.get("swap_approval_history", []):
        swap_histories[history["swap_id"]].append(history)

    results = []
    for truth in ground_truth:
        kind = truth["issue_type"]
        found = False
        if kind == "DOUBLE_BOOKING":
            employee_assignments = by_employee.get(truth["employee_id"], [])
            for i, first in enumerate(employee_assignments):
                for second in employee_assignments[i + 1:]:
                    a = shifts[first["shift_id"]]
                    b = shifts[second["shift_id"]]
                    if a["start_at"] < b["end_at"] and b["start_at"] < a["end_at"]:
                        found = True
                        break
                if found:
                    break
        elif kind == "LEAVE_OVERLAP":
            shift = shifts[truth["shift_id"]]
            leave = next(
                (
                    l for l in leave_by_employee.get(truth["employee_id"], [])
                    if l["leave_id"] == truth["transaction_id"]
                ),
                None,
            )
            found = bool(
                leave
                and leave["start_date"] <= shift["shift_date"] <= leave["end_date"]
                and any(
                    a["shift_id"] == truth["shift_id"]
                    and a["employee_id"] == truth["employee_id"]
                    for a in active
                )
            )
        elif kind == "MISSING_SKILL":
            shift = shifts[truth["shift_id"]]
            template = templates[shift["shift_template_id"]]
            day_type = "HOLIDAY" if shift["shift_date"] in holidays else (
                "WEEKEND" if shift["shift_date"].weekday() >= 5 else "WEEKDAY"
            )
            requirement = next(
                (
                    c for c in coverage
                    if c["team_id"] == shift["team_id"]
                    and c["shift_template_id"] == shift["shift_template_id"]
                    and c["skill_id"] == truth["transaction_id"]
                    and c["day_type"] in ("ALL", day_type)
                ),
                None,
            )
            if requirement:
                qualified = sum(
                    1 for a in by_shift.get(shift["shift_id"], [])
                    if (a["employee_id"], truth["transaction_id"]) in skills
                )
                found = qualified < requirement["min_staff"]
        elif kind == "OVERTIME_CAP":
            employee = employees[truth["employee_id"]]
            week = date.fromisoformat(truth["transaction_id"])
            week_events = [
                e for e in attendance
                if e["employee_id"] == truth["employee_id"]
                and week <= e["scheduled_start"].date() <= week + timedelta(days=6)
            ]
            actual = sum(e["actual_hours"] for e in week_events)
            found = actual > 40 + employee["overtime_cap_weekly"] + 0.01
        elif kind == "UNAPPROVED_SWAP":
            swap = swaps.get(truth["primary_entity_id"])
            found = bool(
                swap
                and swap["status"] == "APPLIED"
                and not any(h["to_status"] == "APPROVED" for h in swap_histories.get(swap["swap_id"], []))
            )
        results.append(
            {
                "ground_truth_id": truth["ground_truth_id"],
                "issue_type": kind,
                "found": found,
            }
        )
    by_type: dict[str, dict] = defaultdict(lambda: {"total": 0, "found": 0})
    for row in results:
        by_type[row["issue_type"]]["total"] += 1
        by_type[row["issue_type"]]["found"] += int(row["found"])
    missing = sum(1 for row in results if not row["found"])
    return {
        "total": len(results),
        "found": len(results) - missing,
        "missing": missing,
        "by_type": dict(by_type),
        "results": results,
    }
