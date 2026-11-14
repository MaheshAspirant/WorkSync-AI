"""OR-Tools CP-SAT scheduling engine.

The engine operates on one team and a date horizon.  It is deliberately
separate from persistence: it receives plain context objects and returns a
plan, so the same code can be unit-tested without a database.

Hard constraints
----------------
* no overlapping assignments / rest-period compliance
* no assignment during approved leave
* only employees of the shift's team
* employee availability (day of week and time window)
* weekly maximum hours (standard + overtime allowance)
* coverage and skill minima where the instance is feasible

Soft constraints
----------------
* minimise overtime
* spread morning / evening / night shifts fairly
* respect shift preferences
* keep staffing close to the minimum required

If the hard-coverage model is infeasible the engine re-solves with coverage as
a soft constraint, returns an explicitly labelled PARTIAL plan and reports the
remaining gaps instead of silently producing an invalid schedule.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as clock_time, timedelta

from ortools.sat.python import cp_model
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.workforce import classify_day, overlaps, rest_gap_hours, week_start
from app.models.attendance import EmployeeAvailability
from app.models.enums import (
    AssignmentStatus,
    DayType,
    EmployeeStatus,
    LeaveStatus,
)
from app.models.leave import LeaveRequest
from app.models.master import Employee, EmployeeSkill, HolidayCalendar, Shift, ShiftTemplate, Team
from app.models.scheduling import CoverageRequirement, ShiftAssignment

ACTIVE_STATUSES = [
    AssignmentStatus.SCHEDULED,
    AssignmentStatus.CONFIRMED,
    AssignmentStatus.COMPLETED,
    AssignmentStatus.SWAPPED_IN,
]

HARD_STATUSES = {"OPTIMAL", "FEASIBLE"}


@dataclass
class EmployeeContext:
    employee: Employee
    skills: set[str]
    availability: dict[int, EmployeeAvailability | None]
    leave_dates: set[date]
    fixed_minutes_by_week: dict[date, int]
    fixed_intervals: list[tuple[datetime, datetime, str]]


@dataclass
class ShiftContext:
    shift: Shift
    total_required: int
    skill_requirements: dict[str, int]
    fixed_assignments: list[ShiftAssignment] = field(default_factory=list)
    fixed_skill_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class PlannedAssignment:
    shift: Shift
    employee: Employee
    skills_used: list[str]
    reason: str
    constraint_evaluation: dict
    optimization_score: float


@dataclass
class CoverageGap:
    shift: Shift
    required: int
    assigned: int
    missing_skills: list[str]
    description: str


@dataclass
class RunResult:
    team_id: str
    status: str
    solver_status: str
    objective_value: float | None
    assignments: list[PlannedAssignment]
    gaps: list[CoverageGap]
    duration_seconds: float
    message: str
    model_stats: dict = field(default_factory=dict)


def _minutes(hours: float) -> int:
    return int(round(hours * 60))


def _load_context(
    db: Session,
    team_id: str,
    start: date,
    end: date,
) -> tuple[Team, list[ShiftContext], dict[str, EmployeeContext], dict[date, DayType]]:
    team = db.get(Team, team_id)
    if team is None:
        raise ValueError(f"Team {team_id} not found")

    shifts = list(
        db.execute(
            select(Shift)
            .where(
                Shift.team_id == team_id,
                Shift.shift_date >= start,
                Shift.shift_date <= end,
                Shift.status != "CANCELLED",
            )
            .order_by(Shift.shift_date, Shift.shift_template_id)
        ).scalars()
    )
    if not shifts:
        return team, [], {}, {}

    employees = list(
        db.execute(
            select(Employee).where(
                Employee.team_id == team_id,
                Employee.status == EmployeeStatus.ACTIVE,
            )
        ).scalars()
    )
    employee_ids = [e.employee_id for e in employees]

    skills_by_employee: dict[str, set[str]] = {}
    for employee_id, skill_id in db.execute(
        select(EmployeeSkill.employee_id, EmployeeSkill.skill_id).where(
            EmployeeSkill.employee_id.in_(employee_ids)
        )
    ):
        skills_by_employee.setdefault(employee_id, set()).add(skill_id)

    availability: dict[str, dict[int, EmployeeAvailability]] = {}
    for row in db.execute(
        select(EmployeeAvailability).where(
            EmployeeAvailability.employee_id.in_(employee_ids),
            EmployeeAvailability.effective_from <= end,
            (EmployeeAvailability.effective_to.is_(None))
            | (EmployeeAvailability.effective_to >= start),
        )
    ).scalars():
        availability.setdefault(row.employee_id, {})[row.day_of_week] = row

    leave_dates: dict[str, set[date]] = {}
    for row in db.execute(
        select(LeaveRequest).where(
            LeaveRequest.employee_id.in_(employee_ids),
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        )
    ).scalars():
        cursor = max(row.start_date, start)
        while cursor <= min(row.end_date, end):
            leave_dates.setdefault(row.employee_id, set()).add(cursor)
            cursor += timedelta(days=1)

    # Existing assignments (including adjacent days for rest checks and full weeks).
    extended_start = start - timedelta(days=2)
    extended_end = end + timedelta(days=2)
    existing = list(
        db.execute(
            select(ShiftAssignment)
            .join(Shift, Shift.shift_id == ShiftAssignment.shift_id)
            .where(
                ShiftAssignment.employee_id.in_(employee_ids),
                ShiftAssignment.status.in_(ACTIVE_STATUSES),
                Shift.shift_date >= extended_start,
                Shift.shift_date <= extended_end,
            )
        ).scalars()
    )
    existing_by_employee: dict[str, list[ShiftAssignment]] = {}
    for assignment in existing:
        existing_by_employee.setdefault(assignment.employee_id, []).append(assignment)

    # Load the shifts referenced by existing assignments.
    existing_shift_ids = {a.shift_id for a in existing}
    existing_shifts = {
        s.shift_id: s
        for s in db.execute(select(Shift).where(Shift.shift_id.in_(existing_shift_ids))).scalars()
    }

    shifts_by_id = {s.shift_id: s for s in shifts}
    shift_assignments: dict[str, list[ShiftAssignment]] = {}
    for assignment in db.execute(
        select(ShiftAssignment).where(
            ShiftAssignment.shift_id.in_(list(shifts_by_id.keys())),
            ShiftAssignment.status.in_(ACTIVE_STATUSES),
        )
    ).scalars():
        shift_assignments.setdefault(assignment.shift_id, []).append(assignment)

    holidays = set(
        db.execute(
            select(HolidayCalendar.holiday_date).where(
                HolidayCalendar.holiday_date >= start,
                HolidayCalendar.holiday_date <= end,
            )
        ).scalars()
    )

    templates = {
        t.shift_template_id: t
        for t in db.execute(
            select(ShiftTemplate).where(
                ShiftTemplate.shift_template_id.in_({s.shift_template_id for s in shifts})
            )
        ).scalars()
    }

    requirement_rows = list(
        db.execute(
            select(CoverageRequirement).where(
                CoverageRequirement.team_id == team_id,
                CoverageRequirement.effective_from <= end,
                (CoverageRequirement.effective_to.is_(None))
                | (CoverageRequirement.effective_to >= start),
            )
        ).scalars()
    )

    def requirements_for(shift: Shift) -> dict[str, int]:
        day_type = classify_day(shift.shift_date, holidays)
        applicable = [
            r
            for r in requirement_rows
            if r.shift_template_id == shift.shift_template_id
            and r.skill_id is not None
            and r.day_type in {DayType.ALL, day_type}
            and r.effective_from <= shift.shift_date
            and (r.effective_to is None or r.effective_to >= shift.shift_date)
        ]
        # Latest effective version wins per skill.
        latest: dict[str, CoverageRequirement] = {}
        for row in applicable:
            current = latest.get(row.skill_id)
            if current is None or row.effective_from > current.effective_from:
                latest[row.skill_id] = row
        return {skill_id: row.min_staff for skill_id, row in latest.items()}

    contexts: list[ShiftContext] = []
    employee_ctx: dict[str, EmployeeContext] = {}
    for employee in employees:
        fixed_by_week: dict[date, int] = {}
        intervals: list[tuple[datetime, datetime, str]] = []
        for assignment in existing_by_employee.get(employee.employee_id, []):
            shift = existing_shifts.get(assignment.shift_id)
            if shift is None:
                continue
            intervals.append((shift.start_at, shift.end_at, shift.shift_id))
            monday = week_start(shift.shift_date)
            fixed_by_week[monday] = fixed_by_week.get(monday, 0) + _minutes(
                assignment.scheduled_hours
            )
        employee_ctx[employee.employee_id] = EmployeeContext(
            employee=employee,
            skills=skills_by_employee.get(employee.employee_id, set()),
            availability=availability.get(employee.employee_id, {}),
            leave_dates=leave_dates.get(employee.employee_id, set()),
            fixed_minutes_by_week=fixed_by_week,
            fixed_intervals=intervals,
        )

    for shift in shifts:
        existing_for_shift = shift_assignments.get(shift.shift_id, [])
        reqs = requirements_for(shift)
        fixed_skill_counts: dict[str, int] = {skill: 0 for skill in reqs}
        for assignment in existing_for_shift:
            employee = next(
                (e for e in employees if e.employee_id == assignment.employee_id), None
            )
            if employee:
                for skill in employee_ctx[employee.employee_id].skills & set(reqs):
                    fixed_skill_counts[skill] += 1
        contexts.append(
            ShiftContext(
                shift=shift,
                total_required=shift.required_staff,
                skill_requirements=reqs,
                fixed_assignments=existing_for_shift,
                fixed_skill_counts=fixed_skill_counts,
            )
        )
    return team, contexts, employee_ctx, {day: classify_day(day, holidays) for day in
                                          (start + timedelta(days=i) for i in range((end - start).days + 1))}


def _availability_ok(ctx: EmployeeContext, shift: Shift) -> bool:
    row = ctx.availability.get(shift.shift_date.weekday())
    if row is None:
        return True
    if not row.is_available:
        return False
    start_clock = shift.start_at.time()
    end_clock = shift.end_at.time()
    if not (row.available_from <= start_clock < row.available_to):
        return False
    if shift.template.crosses_midnight:
        if row.available_from <= row.available_to:
            return end_clock <= row.available_to or end_clock >= clock_time(0, 0)
        return True
    return end_clock <= row.available_to


def _fixed_conflict(ctx: EmployeeContext, shift: Shift) -> bool:
    for start_at, end_at, _shift_id in ctx.fixed_intervals:
        if _shift_id == shift.shift_id:
            return True
        if overlaps(start_at, end_at, shift.start_at, shift.end_at):
            return True
        if end_at <= shift.start_at:
            gap = rest_gap_hours(end_at, shift.start_at)
        else:
            gap = rest_gap_hours(shift.end_at, start_at)
        if gap < ctx.employee.min_rest_hours:
            return True
    return False


def _eligible(ctx: EmployeeContext, shift: Shift, shift_ctx: ShiftContext) -> bool:
    if ctx.employee.employee_id in {a.employee_id for a in shift_ctx.fixed_assignments}:
        return False
    if shift.shift_date in ctx.leave_dates:
        return False
    if not _availability_ok(ctx, shift):
        return False
    if _fixed_conflict(ctx, shift):
        return False
    required_skills = set(shift_ctx.skill_requirements)
    if required_skills and not (ctx.skills & required_skills):
        return False
    minutes = _minutes(shift.template.duration_hours)
    monday = week_start(shift.shift_date)
    cap_minutes = _minutes(ctx.employee.weekly_hours_cap + ctx.employee.overtime_cap_weekly)
    if ctx.fixed_minutes_by_week.get(monday, 0) + minutes > cap_minutes:
        return False
    return True


def _build_model(
    contexts: list[ShiftContext],
    employee_ctx: dict[str, EmployeeContext],
    *,
    relax_coverage: bool,
    use_preferences: bool,
    use_fairness: bool,
) -> tuple[cp_model.CpModel, dict, dict, dict]:
    model = cp_model.CpModel()
    x: dict[tuple[str, str], cp_model.IntVar] = {}
    y: dict[tuple[str, str, str], cp_model.IntVar] = {}
    missing: dict[str, cp_model.IntVar] = {}
    missing_skill: dict[tuple[str, str], cp_model.IntVar] = {}
    overtime: dict[tuple[str, date], cp_model.IntVar] = {}
    max_code: dict[str, cp_model.IntVar] = {}

    eligible_map: dict[str, list[str]] = {}
    for shift_ctx in contexts:
        shift = shift_ctx.shift
        eligible_map[shift.shift_id] = []
        for employee_id, ctx in employee_ctx.items():
            if not _eligible(ctx, shift, shift_ctx):
                continue
            eligible_map[shift.shift_id].append(employee_id)
            var = model.NewBoolVar(f"x_{employee_id}_{shift.shift_id}")
            x[(employee_id, shift.shift_id)] = var
            for skill in ctx.skills & set(shift_ctx.skill_requirements):
                y[(employee_id, shift.shift_id, skill)] = model.NewBoolVar(
                    f"y_{employee_id}_{shift.shift_id}_{skill}"
                )
                model.Add(y[(employee_id, shift.shift_id, skill)] <= var)
            if shift_ctx.skill_requirements:
                model.Add(sum(y.get((employee_id, shift.shift_id, skill), 0)
                              for skill in shift_ctx.skill_requirements) <= var)

    # Coverage and skill constraints.
    for shift_ctx in contexts:
        shift = shift_ctx.shift
        fixed_total = len(shift_ctx.fixed_assignments)
        x_terms = [x[(e, shift.shift_id)] for e in eligible_map[shift.shift_id]]
        needed = max(0, shift_ctx.total_required - fixed_total)
        if relax_coverage:
            miss = model.NewIntVar(0, max(1, needed), f"miss_{shift.shift_id}")
            missing[shift.shift_id] = miss
            model.Add(miss >= needed - sum(x_terms))
        else:
            model.Add(sum(x_terms) >= needed)
        if x_terms:
            model.Add(sum(x_terms) <= needed)

        for skill, minimum in shift_ctx.skill_requirements.items():
            fixed_skill = shift_ctx.fixed_skill_counts.get(skill, 0)
            need_skill = max(0, minimum - fixed_skill)
            skill_terms = [y[(e, shift.shift_id, skill)] for e in eligible_map[shift.shift_id]
                           if (e, shift.shift_id, skill) in y]
            if relax_coverage:
                miss = model.NewIntVar(0, max(1, need_skill), f"missk_{shift.shift_id}_{skill}")
                missing_skill[(shift.shift_id, skill)] = miss
                model.Add(miss >= need_skill - sum(skill_terms))
            else:
                model.Add(sum(skill_terms) >= need_skill)

    # Pairwise overlap / rest constraints per employee.
    shifts_by_employee: dict[str, list[Shift]] = {}
    for shift_ctx in contexts:
        for employee_id in eligible_map[shift_ctx.shift.shift_id]:
            shifts_by_employee.setdefault(employee_id, []).append(shift_ctx.shift)
    for employee_id, shifts in shifts_by_employee.items():
        ordered = sorted(shifts, key=lambda s: s.start_at)
        for i, first in enumerate(ordered):
            for second in ordered[i + 1:]:
                if second.start_at >= first.end_at and rest_gap_hours(
                    first.end_at, second.start_at
                ) >= employee_ctx[employee_id].employee.min_rest_hours:
                    break
                model.Add(
                    x[(employee_id, first.shift_id)] + x[(employee_id, second.shift_id)] <= 1
                )

    # Weekly hours and overtime.
    for employee_id, ctx in employee_ctx.items():
        shifts = shifts_by_employee.get(employee_id, [])
        if not shifts:
            continue
        weeks: dict[date, list[Shift]] = {}
        for shift in shifts:
            weeks.setdefault(week_start(shift.shift_date), []).append(shift)
        for monday, week_shifts in weeks.items():
            terms = [
                _minutes(s.template.duration_hours) * x[(employee_id, s.shift_id)]
                for s in week_shifts
                if (employee_id, s.shift_id) in x
            ]
            if not terms:
                continue
            fixed = ctx.fixed_minutes_by_week.get(monday, 0)
            cap = _minutes(ctx.employee.weekly_hours_cap)
            ot_cap = _minutes(ctx.employee.overtime_cap_weekly)
            model.Add(sum(terms) + fixed <= cap + ot_cap)
            ot = model.NewIntVar(0, ot_cap, f"ot_{employee_id}_{monday.isoformat()}")
            overtime[(employee_id, monday)] = ot
            model.Add(ot >= sum(terms) + fixed - cap)

    # Fairness: flatten counts of each shift code across eligible employees.
    if use_fairness:
        for code in ("A", "B", "C"):
            counts = []
            for employee_id, shifts in shifts_by_employee.items():
                code_terms = [
                    x[(employee_id, s.shift_id)]
                    for s in shifts
                    if s.template.code == code and (employee_id, s.shift_id) in x
                ]
                if code_terms:
                    counts.append(sum(code_terms))
            if counts:
                max_var = model.NewIntVar(0, max(1, len(shifts_by_employee)), f"max_{code}")
                for count in counts:
                    model.Add(max_var >= count)
                max_code[code] = max_var

    objective_terms = []
    if relax_coverage:
        objective_terms.extend([10000 * var for var in missing.values()])
        objective_terms.extend([5000 * var for var in missing_skill.values()])
    objective_terms.extend([10 * var for var in overtime.values()])
    if use_fairness:
        weights = {"C": 5, "B": 3, "A": 1}
        for code, var in max_code.items():
            objective_terms.append(weights[code] * var)
    if use_preferences:
        for (employee_id, shift_id), var in x.items():
            shift = next(s for s in shifts_by_employee.get(employee_id, []) if s.shift_id == shift_id)
            preferred = employee_ctx[employee_id].employee.preferred_shift.value
            if preferred == {"A": "MORNING", "B": "EVENING", "C": "NIGHT"}.get(
                shift.template.code, "NONE"
            ):
                objective_terms.append(-2 * var)
    model.Minimize(sum(objective_terms)) if objective_terms else None
    return model, x, y, {"missing": missing, "missing_skill": missing_skill,
                         "overtime": overtime, "max_code": max_code}


def _solve(
    contexts: list[ShiftContext],
    employee_ctx: dict[str, EmployeeContext],
    *,
    relax_coverage: bool,
    time_limit: float,
    use_preferences: bool,
    use_fairness: bool,
) -> tuple[str, float | None, list[PlannedAssignment], list[CoverageGap], dict]:
    started = time.perf_counter()
    model, x, y, extras = _build_model(
        contexts,
        employee_ctx,
        relax_coverage=relax_coverage,
        use_preferences=use_preferences,
        use_fairness=use_fairness,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(1.0, time_limit)
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    status_name = solver.StatusName(status)
    plans: list[PlannedAssignment] = []
    gaps: list[CoverageGap] = []

    if status_name in HARD_STATUSES:
        for shift_ctx in contexts:
            shift = shift_ctx.shift
            selected = [
                e for e in employee_ctx
                if (e, shift.shift_id) in x and solver.Value(x[(e, shift.shift_id)]) == 1
            ]
            for employee_id in selected:
                ctx = employee_ctx[employee_id]
                employee = ctx.employee
                skills_used = sorted(ctx.skills & set(shift_ctx.skill_requirements))
                required_skills = sorted(shift_ctx.skill_requirements)
                fixed_total = len(shift_ctx.fixed_assignments)
                eval_data = {
                    "skill_match": bool(skills_used),
                    "skills_required": required_skills,
                    "skills_held": skills_used,
                    "availability_result": "AVAILABLE",
                    "leave_eligible": shift.shift_date not in ctx.leave_dates,
                    "leave_check": "No approved leave on shift date"
                    if shift.shift_date not in ctx.leave_dates
                    else "Approved leave overlaps shift date",
                    "team_eligible": employee.team_id == shift.team_id,
                    "weekly_hours_before": round(
                        ctx.fixed_minutes_by_week.get(week_start(shift.shift_date), 0) / 60, 2
                    ),
                    "weekly_cap": employee.weekly_hours_cap,
                    "overtime_cap": employee.overtime_cap_weekly,
                    "min_rest_hours": employee.min_rest_hours,
                    "preference_match": employee.preferred_shift.value
                    == {"A": "MORNING", "B": "EVENING", "C": "NIGHT"}.get(
                        shift.template.code, "NONE"
                    ),
                    "fixed_assignments_already_on_shift": fixed_total,
                    "coverage_requirement": shift_ctx.total_required,
                    "skill_requirements": shift_ctx.skill_requirements,
                }
                score = 100.0
                if eval_data["weekly_hours_before"] >= employee.weekly_hours_cap:
                    score -= 15
                if not eval_data["preference_match"]:
                    score -= 10
                if skills_used:
                    score += 5
                if shift.template.code == "C":
                    score -= 5
                reasons = [
                    f"Skill match: holds {', '.join(skills_used) or 'no required skill'}",
                    "Availability: available on this weekday/time window",
                    "Leave: no approved leave on " + str(shift.shift_date),
                    f"Hours: {eval_data['weekly_hours_before']:.1f}h already scheduled this week "
                    f"(cap {employee.weekly_hours_cap:.0f}h)",
                ]
                if eval_data["preference_match"]:
                    reasons.append(f"Preference: matches preferred {employee.preferred_shift.value} shift")
                reasons.append(
                    f"Coverage: fills one of {shift_ctx.total_required} required positions on {shift.shift_id}"
                )
                plans.append(
                    PlannedAssignment(
                        shift=shift,
                        employee=employee,
                        skills_used=skills_used,
                        reason="; ".join(reasons) + ".",
                        constraint_evaluation=eval_data,
                        optimization_score=round(max(0.0, min(100.0, score)), 2),
                    )
                )
            assigned_total = len(selected) + len(shift_ctx.fixed_assignments)
            missing_skills = []
            assigned_skill_counts: dict[str, int] = {}
            for assignment in shift_ctx.fixed_assignments:
                ctx = employee_ctx.get(assignment.employee_id)
                if ctx:
                    for skill in ctx.skills & set(shift_ctx.skill_requirements):
                        assigned_skill_counts[skill] = assigned_skill_counts.get(skill, 0) + 1
            for employee_id in selected:
                for skill in employee_ctx[employee_id].skills & set(shift_ctx.skill_requirements):
                    assigned_skill_counts[skill] = assigned_skill_counts.get(skill, 0) + 1
            for skill, minimum in shift_ctx.skill_requirements.items():
                if assigned_skill_counts.get(skill, 0) < minimum:
                    missing_skills.append(skill)
            if assigned_total < shift_ctx.total_required or missing_skills:
                gap = shift_ctx.total_required - assigned_total
                gaps.append(
                    CoverageGap(
                        shift=shift,
                        required=shift_ctx.total_required,
                        assigned=assigned_total,
                        missing_skills=missing_skills,
                        description=(
                            f"{shift.shift_id}: {assigned_total}/{shift_ctx.total_required} positions filled"
                            + (f"; missing skills {', '.join(missing_skills)}" if missing_skills else "")
                        ),
                    )
                )
    duration = round(time.perf_counter() - started, 3)
    objective = solver.ObjectiveValue() if status_name in HARD_STATUSES else None
    return status_name, objective, plans, gaps, {
        "duration_seconds": duration,
        "relaxed": relax_coverage,
        "variables": len(x),
        "constraints": len(model.Proto().constraints),
    }


def generate_team_schedule(
    db: Session,
    *,
    team_id: str,
    start: date,
    end: date,
    time_limit_seconds: float = 12.0,
    use_preferences: bool = True,
    use_fairness: bool = True,
) -> RunResult:
    team, contexts, employee_ctx, _day_types = _load_context(db, team_id, start, end)
    if not contexts:
        return RunResult(
            team_id=team_id,
            status="COMPLETED",
            solver_status="NOT_RUN",
            objective_value=0.0,
            assignments=[],
            gaps=[],
            duration_seconds=0.0,
            message="No shifts in scope.",
        )
    status_name, objective, plans, gaps, stats = _solve(
        contexts,
        employee_ctx,
        relax_coverage=False,
        time_limit=time_limit_seconds,
        use_preferences=use_preferences,
        use_fairness=use_fairness,
    )
    relaxed = False
    if status_name not in HARD_STATUSES:
        relaxed = True
        status_name, objective, plans, gaps, stats = _solve(
            contexts,
            employee_ctx,
            relax_coverage=True,
            time_limit=time_limit_seconds,
            use_preferences=use_preferences,
            use_fairness=use_fairness,
        )
    if status_name not in HARD_STATUSES:
        return RunResult(
            team_id=team_id,
            status="INFEASIBLE",
            solver_status=status_name,
            objective_value=None,
            assignments=[],
            gaps=[
                CoverageGap(
                    shift=ctx.shift,
                    required=ctx.total_required,
                    assigned=len(ctx.fixed_assignments),
                    missing_skills=sorted(ctx.skill_requirements),
                    description=f"{ctx.shift.shift_id}: no feasible assignment found",
                )
                for ctx in contexts
            ],
            duration_seconds=stats["duration_seconds"],
            message="No feasible or partial schedule could be produced for this scope.",
            model_stats=stats,
        )
    run_status = "PARTIAL" if gaps else "COMPLETED"
    message = (
        f"Partial schedule: {len(gaps)} coverage gap(s) reported explicitly."
        if gaps
        else "Feasible schedule generated with all coverage requirements met."
    )
    if relaxed:
        message += " Coverage was relaxed because the hard model was infeasible."
    return RunResult(
        team_id=team_id,
        status=run_status,
        solver_status=status_name,
        objective_value=objective,
        assignments=plans,
        gaps=gaps,
        duration_seconds=stats["duration_seconds"],
        message=message,
        model_stats=stats,
    )
