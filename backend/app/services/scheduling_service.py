"""Scheduling orchestration: run lifecycle, persistence and explainability."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import managed_team_ids
from app.audit.service import record_audit
from app.core.config import settings
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.core.ids import next_id
from app.core.workforce import week_start
from app.db.base import utcnow
from app.models.auth import User
from app.models.enums import (
    AssignmentSource,
    AssignmentStatus,
    IssueType,
    RoleName,
    RunStatus,
    Severity,
    ShiftStatus,
    SolverStatus,
)
from app.models.master import Employee, Shift, Team
from app.models.scheduling import (
    SchedulingDecision,
    SchedulingException,
    SchedulingRun,
    ShiftAssignment,
)
from app.scheduling.engine import generate_team_schedule
from app.schemas.scheduling import GenerateScheduleRequest

ACTIVE_ASSIGNMENT_STATUSES = [
    AssignmentStatus.SCHEDULED,
    AssignmentStatus.CONFIRMED,
    AssignmentStatus.SWAPPED_IN,
]


def _assert_run_access(db: Session, user: User, run: SchedulingRun) -> None:
    role = user.role_value
    if role in {RoleName.ADMIN, RoleName.HR}:
        return
    if role == RoleName.MANAGER:
        if run.team_id and run.team_id in managed_team_ids(db, user):
            return
        raise PermissionDeniedError("You can only view scheduling runs for your teams")
    raise PermissionDeniedError("Employees cannot view scheduling runs")


def _cancel_existing(db: Session, actor: User, team_id: str, start: date, end: date) -> int:
    assignments = list(
        db.execute(
            select(ShiftAssignment)
            .join(Shift, Shift.shift_id == ShiftAssignment.shift_id)
            .where(
                Shift.team_id == team_id,
                Shift.shift_date >= start,
                Shift.shift_date <= end,
                ShiftAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
            )
        ).scalars()
    )
    for assignment in assignments:
        assignment.status = AssignmentStatus.CANCELLED
        assignment.notes = (assignment.notes or "") + " | Cancelled by schedule regeneration"
    if assignments:
        record_audit(
            db, actor, "CANCEL_ASSIGNMENTS_FOR_REGENERATION", "ShiftAssignment", None,
            previous={"count": len(assignments)},
            new={"assignment_ids": [a.assignment_id for a in assignments]},
            reason="replace_existing scheduling run",
        )
    return len(assignments)


def _persist_gap_exceptions(db: Session, run_id: str, gaps) -> int:
    count = 0
    for gap in gaps:
        fingerprint = f"COVERAGE_GAP|-|{gap.shift.shift_id}|-|{gap.shift.team_id}"[:220]
        existing = db.execute(
            select(SchedulingException).where(SchedulingException.fingerprint == fingerprint)
        ).scalar_one_or_none()
        if existing:
            existing.run_id = existing.run_id or run_id
            count += 1
            continue
        db.add(
            SchedulingException(
                issue_id=next_id(db, "issue", "ISS", 6, year=date.today().year),
                run_id=run_id,
                issue_type=IssueType.COVERAGE_GAP,
                shift_id=gap.shift.shift_id,
                transaction_type="TEAM",
                transaction_id=gap.shift.team_id,
                severity=Severity.HIGH,
                description=gap.description,
                detection_source="SCHEDULER",
                fingerprint=fingerprint,
            )
        )
        count += 1
        for skill in gap.missing_skills:
            skill_fp = f"MISSING_SKILL|-|{gap.shift.shift_id}|-|{skill}"[:220]
            if db.execute(
                select(SchedulingException).where(SchedulingException.fingerprint == skill_fp)
            ).scalar_one_or_none():
                continue
            db.add(
                SchedulingException(
                    issue_id=next_id(db, "issue", "ISS", 6, year=date.today().year),
                    run_id=run_id,
                    issue_type=IssueType.MISSING_SKILL,
                    shift_id=gap.shift.shift_id,
                    transaction_type="SKILL",
                    transaction_id=skill,
                    severity=Severity.HIGH,
                    description=f"{gap.shift.shift_id}: required skill {skill} is not covered.",
                    detection_source="SCHEDULER",
                    fingerprint=skill_fp,
                )
            )
            count += 1
    return count


def generate_schedule(db: Session, actor: User, payload: GenerateScheduleRequest) -> SchedulingRun:
    if payload.end_date < payload.start_date:
        raise ValidationError("end_date must be on or after start_date")
    horizon = (payload.end_date - payload.start_date).days + 1
    if horizon > settings.scheduler_max_horizon_days:
        raise ValidationError(
            f"Scheduling horizon cannot exceed {settings.scheduler_max_horizon_days} days"
        )
    if payload.team_id:
        team = db.get(Team, payload.team_id)
        if team is None:
            raise NotFoundError("Team not found")
        if actor.role_value == RoleName.MANAGER and payload.team_id not in managed_team_ids(db, actor):
            raise PermissionDeniedError("You can only schedule teams you manage")
        team_ids = [payload.team_id]
    else:
        if actor.role_value not in {RoleName.ADMIN, RoleName.HR}:
            raise PermissionDeniedError("Only HR/Admin can schedule across all teams")
        team_ids = list(
            db.execute(
                select(Shift.team_id)
                .where(Shift.shift_date >= payload.start_date, Shift.shift_date <= payload.end_date)
                .distinct()
                .order_by(Shift.team_id)
            ).scalars()
        )
    if not team_ids:
        raise ValidationError("No shifts exist in the requested scope")

    time_limit = payload.time_limit_seconds or settings.scheduler_time_limit_seconds
    run = SchedulingRun(
        run_id=next_id(db, "run", "RUN", 6, year=payload.start_date.year),
        team_id=payload.team_id,
        scope_start=payload.start_date,
        scope_end=payload.end_date,
        status=RunStatus.RUNNING,
        solver_status=SolverStatus.NOT_RUN,
        parameters={
            "team_ids": team_ids,
            "use_preferences": payload.use_preferences,
            "use_fairness": payload.use_fairness,
            "time_limit_seconds": time_limit,
            "replace_existing": payload.replace_existing,
        },
        created_by_user_id=actor.user_id,
        started_at=utcnow(),
    )
    db.add(run)
    db.flush()

    total_assignments = 0
    total_gaps = 0
    statuses: list[str] = []
    solver_statuses: list[str] = []
    objective_total = 0.0
    scores: list[float] = []
    messages: list[str] = []
    durations: list[float] = []

    for team_id in team_ids:
        if payload.replace_existing:
            _cancel_existing(db, actor, team_id, payload.start_date, payload.end_date)
            db.flush()
        result = generate_team_schedule(
            db,
            team_id=team_id,
            start=payload.start_date,
            end=payload.end_date,
            time_limit_seconds=time_limit,
            use_preferences=payload.use_preferences,
            use_fairness=payload.use_fairness,
        )
        statuses.append(result.status)
        solver_statuses.append(result.solver_status)
        if result.objective_value is not None:
            objective_total += result.objective_value
        durations.append(result.duration_seconds)
        messages.append(f"{team_id}: {result.message}")
        for plan in result.assignments:
            duplicate = db.execute(
                select(ShiftAssignment).where(
                    ShiftAssignment.shift_id == plan.shift.shift_id,
                    ShiftAssignment.employee_id == plan.employee.employee_id,
                    ShiftAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                )
            ).scalars().first()
            if duplicate:
                # Defensive guard; the solver excludes existing active assignees.
                continue
            assignment_id = next_id(db, "assignment", "ASG", 6)
            assignment = ShiftAssignment(
                assignment_id=assignment_id,
                shift_id=plan.shift.shift_id,
                employee_id=plan.employee.employee_id,
                status=AssignmentStatus.SCHEDULED,
                assignment_source=AssignmentSource.OPTIMIZER,
                assigned_at=utcnow(),
                scheduled_hours=plan.shift.template.duration_hours,
                is_overtime=plan.constraint_evaluation.get("weekly_hours_before", 0)
                >= plan.employee.weekly_hours_cap,
                run_id=run.run_id,
                notes="Generated by OR-Tools CP-SAT scheduling run",
            )
            db.add(assignment)
            db.add(
                SchedulingDecision(
                    run_id=run.run_id,
                    shift_id=plan.shift.shift_id,
                    employee_id=plan.employee.employee_id,
                    assignment_id=assignment_id,
                    reason=plan.reason,
                    skill_match=bool(plan.skills_used),
                    availability_result=plan.constraint_evaluation["availability_result"],
                    leave_eligible=plan.constraint_evaluation["leave_eligible"],
                    constraint_evaluation=plan.constraint_evaluation,
                    optimization_score=plan.optimization_score,
                )
            )
            total_assignments += 1
            scores.append(plan.optimization_score)
        total_gaps += len(result.gaps)
        _persist_gap_exceptions(db, run.run_id, result.gaps)
        db.flush()

    if "INFEASIBLE" in statuses and all(s == "INFEASIBLE" for s in statuses):
        run.status = RunStatus.INFEASIBLE
    elif "INFEASIBLE" in statuses or "PARTIAL" in statuses:
        run.status = RunStatus.PARTIAL
    else:
        run.status = RunStatus.COMPLETED
    if "INFEASIBLE" in solver_statuses:
        run.solver_status = SolverStatus.INFEASIBLE
    elif "UNKNOWN" in solver_statuses:
        run.solver_status = SolverStatus.UNKNOWN
    elif "FEASIBLE" in solver_statuses:
        run.solver_status = SolverStatus.FEASIBLE
    elif "OPTIMAL" in solver_statuses:
        run.solver_status = SolverStatus.OPTIMAL
    else:
        run.solver_status = SolverStatus.NOT_RUN

    run.objective_value = round(objective_total, 2) if solver_statuses else None
    run.assignments_created = total_assignments
    run.coverage_gaps = total_gaps
    run.hard_violations = 0  # the solver never emits a plan that violates hard constraints
    run.soft_score = round(sum(scores) / len(scores), 2) if scores else None
    run.duration_seconds = round(sum(durations), 3)
    run.completed_at = utcnow()
    run.parameters = {
        **run.parameters,
        "message": " ".join(messages),
        "teams_processed": len(team_ids),
        "model_stats": {"teams": len(team_ids)},
    }
    record_audit(
        db, actor, "GENERATE_SCHEDULE", "SchedulingRun", run.run_id,
        new={
            "team_ids": team_ids,
            "scope": [str(payload.start_date), str(payload.end_date)],
            "assignments": total_assignments,
            "coverage_gaps": total_gaps,
            "status": run.status.value,
        },
    )
    db.commit()
    return get_run(db, actor, run.run_id)


def list_runs(db: Session, user: User, *, page: int = 1, page_size: int = 20,
              status: RunStatus | None = None) -> tuple[list[SchedulingRun], int]:
    stmt = select(SchedulingRun)
    role = user.role_value
    if role == RoleName.MANAGER:
        teams = managed_team_ids(db, user)
        stmt = stmt.where(SchedulingRun.team_id.in_(teams or ["__none__"]))
    elif role not in {RoleName.ADMIN, RoleName.HR}:
        raise PermissionDeniedError("Employees cannot view scheduling runs")
    if status:
        stmt = stmt.where(SchedulingRun.status == status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(SchedulingRun.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars()
    )
    return rows, total


def get_run(db: Session, user: User, run_id: str) -> SchedulingRun:
    run = db.execute(
        select(SchedulingRun)
        .options(
            selectinload(SchedulingRun.decisions).joinedload(SchedulingDecision.employee),
            selectinload(SchedulingRun.decisions).joinedload(SchedulingDecision.shift).joinedload(Shift.template),
            selectinload(SchedulingRun.exceptions),
        )
        .where(SchedulingRun.run_id == run_id)
    ).unique().scalar_one_or_none()
    if run is None:
        raise NotFoundError("Scheduling run not found")
    _assert_run_access(db, user, run)
    return run


def list_assignments(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 25,
    team_id: str | None = None,
    employee_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> tuple[list[ShiftAssignment], int]:
    stmt = select(ShiftAssignment).join(Shift, Shift.shift_id == ShiftAssignment.shift_id).options(
        joinedload(ShiftAssignment.employee),
        joinedload(ShiftAssignment.shift).joinedload(Shift.template),
        joinedload(ShiftAssignment.shift).joinedload(Shift.team),
    )
    role = user.role_value
    if role == RoleName.EMPLOYEE:
        stmt = stmt.where(ShiftAssignment.employee_id == (user.employee_id or "__none__"))
    elif role == RoleName.MANAGER:
        teams = managed_team_ids(db, user)
        stmt = stmt.where(Shift.team_id.in_(teams or ["__none__"]))
    if team_id:
        stmt = stmt.where(Shift.team_id == team_id)
    if employee_id:
        stmt = stmt.where(ShiftAssignment.employee_id == employee_id)
    if start:
        stmt = stmt.where(Shift.shift_date >= start)
    if end:
        stmt = stmt.where(Shift.shift_date <= end)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(Shift.start_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().scalars()
    )
    return rows, total


def list_shifts(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 50,
    team_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> tuple[list[Shift], int]:
    stmt = select(Shift).options(
        joinedload(Shift.template),
        joinedload(Shift.team),
    )
    role = user.role_value
    if role == RoleName.EMPLOYEE:
        employee = db.get(Employee, user.employee_id) if user.employee_id else None
        stmt = stmt.where(Shift.team_id == (employee.team_id if employee else "__none__"))
    elif role == RoleName.MANAGER:
        teams = managed_team_ids(db, user)
        stmt = stmt.where(Shift.team_id.in_(teams or ["__none__"]))
    if team_id:
        stmt = stmt.where(Shift.team_id == team_id)
    if start:
        stmt = stmt.where(Shift.shift_date >= start)
    if end:
        stmt = stmt.where(Shift.shift_date <= end)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(Shift.shift_date, Shift.shift_template_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().scalars()
    )
    return rows, total
