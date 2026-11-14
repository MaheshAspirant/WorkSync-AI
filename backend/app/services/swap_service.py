"""Shift-swap lifecycle with target agreement, manager approval and history."""

from __future__ import annotations

from datetime import date, timedelta

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
from app.core.ids import next_id
from app.core.workforce import (
    classify_day,
    overlaps,
    rest_gap_hours,
    week_bounds,
)
from app.db.base import utcnow
from app.models.attendance import EmployeeAvailability
from app.models.auth import User
from app.models.enums import (
    AssignmentSource,
    AssignmentStatus,
    DayType,
    LeaveStatus,
    RoleName,
    ShiftStatus,
    SwapStatus,
)
from app.models.leave import LeaveRequest
from app.models.master import Employee, EmployeeSkill, HolidayCalendar, Shift
from app.models.scheduling import (
    CoverageRequirement,
    ShiftAssignment as AssignmentModel,
    SwapApprovalHistory,
    SwapRequest,
)

ACTIVE_ASSIGNMENT_STATUSES = [
    AssignmentStatus.SCHEDULED,
    AssignmentStatus.CONFIRMED,
    AssignmentStatus.COMPLETED,
    AssignmentStatus.SWAPPED_IN,
]


def _assignment(db: Session, assignment_id: str) -> AssignmentModel:
    row = db.execute(
        select(AssignmentModel)
        .options(
            joinedload(AssignmentModel.shift).joinedload(Shift.template),
            joinedload(AssignmentModel.shift).joinedload(Shift.team),
            joinedload(AssignmentModel.employee),
        )
        .where(AssignmentModel.assignment_id == assignment_id)
    ).unique().scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"Assignment {assignment_id} not found")
    return row


def _visible_swap_stmt(db: Session, user: User):
    stmt = select(SwapRequest).options(
        joinedload(SwapRequest.requester),
        joinedload(SwapRequest.target),
        joinedload(SwapRequest.requester_assignment).joinedload(AssignmentModel.shift).joinedload(Shift.template),
        joinedload(SwapRequest.target_assignment).joinedload(AssignmentModel.shift).joinedload(Shift.template),
        joinedload(SwapRequest.approvals),
    )
    role = user.role_value
    if role in {RoleName.ADMIN, RoleName.HR}:
        return stmt
    if role == RoleName.MANAGER:
        teams = managed_team_ids(db, user)
        if not teams:
            return stmt.where(SwapRequest.swap_id == "__none__")
        return stmt.join(
            Employee, Employee.employee_id == SwapRequest.requester_employee_id
        ).where(Employee.team_id.in_(teams))
    return stmt.where(
        (SwapRequest.requester_employee_id == (user.employee_id or "__none__"))
        | (SwapRequest.target_employee_id == (user.employee_id or "__none__"))
    )


def list_swaps(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 25,
    status: SwapStatus | None = None,
) -> tuple[list[SwapRequest], int]:
    stmt = _visible_swap_stmt(db, user)
    if status:
        stmt = stmt.where(SwapRequest.status == status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(SwapRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().scalars()
    )
    return rows, total


def get_swap(db: Session, user: User, swap_id: str) -> SwapRequest:
    row = db.execute(
        _visible_swap_stmt(db, user).where(SwapRequest.swap_id == swap_id)
    ).unique().scalar_one_or_none()
    if row is None:
        raise NotFoundError("Swap request not found")
    return row


def _history(db: Session, swap: SwapRequest, actor: User | None,
             from_status: SwapStatus | None, to_status: SwapStatus, action: str,
             comment: str | None = None) -> None:
    entry = SwapApprovalHistory(
        swap_id=swap.swap_id,
        from_status=from_status,
        to_status=to_status,
        action=action,
        actor_user_id=actor.user_id if actor else None,
        comment=comment,
    )
    swap.approvals.append(entry)


def _skill_ids(db: Session, employee_id: str) -> set[str]:
    return set(
        db.execute(
            select(EmployeeSkill.skill_id).where(EmployeeSkill.employee_id == employee_id)
        ).scalars()
    )


def _required_skills(db: Session, shift: Shift) -> set[str]:
    holiday = db.execute(
        select(HolidayCalendar.holiday_date).where(HolidayCalendar.holiday_date == shift.shift_date)
    ).scalar_one_or_none()
    day_type = classify_day(shift.shift_date, {holiday} if holiday else set())
    rows = db.execute(
        select(CoverageRequirement).where(
            CoverageRequirement.team_id == shift.team_id,
            CoverageRequirement.shift_template_id == shift.shift_template_id,
            CoverageRequirement.day_type.in_([DayType.ALL, day_type]),
            CoverageRequirement.skill_id.is_not(None),
            CoverageRequirement.effective_from <= shift.shift_date,
            (CoverageRequirement.effective_to.is_(None))
            | (CoverageRequirement.effective_to >= shift.shift_date),
        )
    ).scalars()
    return {r.skill_id for r in rows if r.skill_id}


def _leave_conflict(db: Session, employee_id: str, shift: Shift) -> LeaveRequest | None:
    return db.execute(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.start_date <= shift.shift_date,
            LeaveRequest.end_date >= shift.shift_date,
        )
    ).scalars().first()


def _availability_conflict(db: Session, employee_id: str, shift: Shift) -> str | None:
    rows = list(
        db.execute(
            select(EmployeeAvailability).where(
                EmployeeAvailability.employee_id == employee_id,
                EmployeeAvailability.day_of_week == shift.shift_date.weekday(),
                (EmployeeAvailability.effective_to.is_(None))
                | (EmployeeAvailability.effective_to >= shift.shift_date),
            )
        ).scalars()
    )
    if not rows:
        return None
    usable = [r for r in rows if r.effective_from <= shift.shift_date]
    if not usable:
        return None
    if not any(r.is_available for r in usable):
        return f"Employee is not available on {shift.shift_date.strftime('%A')}"
    return None


def _weekly_hours(db: Session, employee_id: str, shift: Shift, exclude_assignment_id: str | None) -> float:
    monday, sunday = week_bounds(shift.shift_date)
    stmt = (
        select(func.coalesce(func.sum(AssignmentModel.scheduled_hours), 0.0))
        .join(Shift, Shift.shift_id == AssignmentModel.shift_id)
        .where(
            AssignmentModel.employee_id == employee_id,
            AssignmentModel.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
            Shift.shift_date >= monday,
            Shift.shift_date <= sunday,
        )
    )
    if exclude_assignment_id:
        stmt = stmt.where(AssignmentModel.assignment_id != exclude_assignment_id)
    return float(db.execute(stmt).scalar_one())


def _rest_conflicts(db: Session, employee_id: str, shift: Shift,
                    exclude_assignment_id: str | None) -> list[str]:
    stmt = (
        select(AssignmentModel)
        .options(joinedload(AssignmentModel.shift))
        .join(Shift, Shift.shift_id == AssignmentModel.shift_id)
        .where(
            AssignmentModel.employee_id == employee_id,
            AssignmentModel.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
            Shift.shift_date >= shift.shift_date - timedelta(days=2),
            Shift.shift_date <= shift.shift_date + timedelta(days=2),
        )
    )
    if exclude_assignment_id:
        stmt = stmt.where(AssignmentModel.assignment_id != exclude_assignment_id)
    conflicts = []
    employee = db.get(Employee, employee_id)
    min_rest = employee.min_rest_hours if employee else 11.0
    for other in db.execute(stmt).scalars():
        if other.shift_id == shift.shift_id:
            continue
        if overlaps(shift.start_at, shift.end_at, other.shift.start_at, other.shift.end_at):
            conflicts.append(f"overlaps assignment {other.assignment_id}")
            continue
        if other.shift.end_at <= shift.start_at:
            gap = rest_gap_hours(other.shift.end_at, shift.start_at)
        else:
            gap = rest_gap_hours(shift.end_at, other.shift.start_at)
        if gap < min_rest:
            conflicts.append(
                f"rest gap of {gap:.1f}h with {other.assignment_id} is below {min_rest:.0f}h"
            )
    return conflicts


def evaluate_swap(db: Session, requester_assignment: AssignmentModel,
                  target_assignment: AssignmentModel) -> list[str]:
    """Return a list of blocking issues for a proposed swap (empty = valid)."""
    issues: list[str] = []
    requester = requester_assignment.employee
    target = target_assignment.employee
    requester_shift = requester_assignment.shift
    target_shift = target_assignment.shift

    if requester.employee_id == target.employee_id:
        issues.append("Requester and target must be different employees")
    if requester_shift.shift_id == target_shift.shift_id:
        issues.append("Both assignments refer to the same shift")
    if requester_assignment.status.value not in {s.value for s in ACTIVE_ASSIGNMENT_STATUSES}:
        issues.append("Requester assignment is not active")
    if target_assignment.status.value not in {s.value for s in ACTIVE_ASSIGNMENT_STATUSES}:
        issues.append("Target assignment is not active")
    if requester.team_id != requester_shift.team_id or target.team_id != target_shift.team_id:
        issues.append("Assignment does not belong to the employee's team")

    # Skill compatibility in both directions.
    requester_skills = _skill_ids(db, requester.employee_id)
    target_skills = _skill_ids(db, target.employee_id)
    required_for_target = _required_skills(db, target_shift)
    required_for_requester = _required_skills(db, requester_shift)
    if required_for_target and not (requester_skills & required_for_target):
        issues.append("Requester does not hold any skill required by the target shift")
    if required_for_requester and not (target_skills & required_for_requester):
        issues.append("Target employee does not hold any skill required by the requester shift")

    for employee, shift, label in (
        (requester, target_shift, "Requester"),
        (target, requester_shift, "Target"),
    ):
        leave = _leave_conflict(db, employee.employee_id, shift)
        if leave:
            issues.append(f"{label} has approved leave {leave.leave_id} on {shift.shift_date}")
        availability_issue = _availability_conflict(db, employee.employee_id, shift)
        if availability_issue:
            issues.append(f"{label}: {availability_issue}")
        own_assignment = requester_assignment if employee is requester else target_assignment
        weekly = _weekly_hours(
            db, employee.employee_id, shift, exclude_assignment_id=own_assignment.assignment_id
        )
        schedule_cap = employee.weekly_hours_cap + employee.overtime_cap_weekly
        if weekly + shift.template.duration_hours > schedule_cap:
            issues.append(
                f"{label} would reach {weekly + shift.template.duration_hours:.1f}h in the week, "
                f"above the {schedule_cap:.0f}h cap"
            )
        rest = _rest_conflicts(
            db, employee.employee_id, shift,
            exclude_assignment_id=own_assignment.assignment_id,
        )
        if rest:
            issues.append(f"{label}: " + "; ".join(rest))
    return issues


def swap_candidates(db: Session, user: User, start: date, end: date) -> list[AssignmentModel]:
    """Active future assignments the caller may propose for a swap.

    Employees see their own team so they can choose a partner; managers see the
    teams they manage; HR/Admin see everything.
    """
    stmt = (
        select(AssignmentModel)
        .options(
            joinedload(AssignmentModel.employee),
            joinedload(AssignmentModel.shift).joinedload(Shift.template),
            joinedload(AssignmentModel.shift).joinedload(Shift.team),
        )
        .join(Shift, Shift.shift_id == AssignmentModel.shift_id)
        .where(
            AssignmentModel.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
            Shift.shift_date >= start,
            Shift.shift_date <= end,
        )
    )
    role = user.role_value
    if role == RoleName.EMPLOYEE:
        employee = db.get(Employee, user.employee_id) if user.employee_id else None
        stmt = stmt.where(Shift.team_id == (employee.team_id if employee else "__none__"))
    elif role == RoleName.MANAGER:
        teams = managed_team_ids(db, user)
        stmt = stmt.where(Shift.team_id.in_(teams or ["__none__"]))
    return list(db.execute(stmt.order_by(Shift.start_at).limit(500)).unique().scalars())


def create_swap(db: Session, user: User, requester_assignment_id: str,
                target_assignment_id: str, reason: str) -> SwapRequest:
    requester_assignment = _assignment(db, requester_assignment_id)
    target_assignment = _assignment(db, target_assignment_id)
    if user.role_value not in {RoleName.ADMIN, RoleName.HR}:
        if user.employee_id != requester_assignment.employee_id:
            raise PermissionDeniedError("You can only request a swap for your own assignment")
    if requester_assignment.status.value not in {s.value for s in ACTIVE_ASSIGNMENT_STATUSES}:
        raise ConflictError("Requester assignment is not active")
    if target_assignment.status.value not in {s.value for s in ACTIVE_ASSIGNMENT_STATUSES}:
        raise ConflictError("Target assignment is not active")
    if requester_assignment.employee_id == target_assignment.employee_id:
        raise ValidationError("Cannot swap an assignment with yourself")
    if requester_assignment.shift_id == target_assignment.shift_id:
        raise ValidationError("Both assignments refer to the same shift")
    existing = db.execute(
        select(SwapRequest).where(
            SwapRequest.requester_assignment_id == requester_assignment_id,
            SwapRequest.status.in_([SwapStatus.REQUESTED, SwapStatus.APPROVED]),
        )
    ).scalars().first()
    if existing:
        raise ConflictError(f"An open swap already exists for this assignment ({existing.swap_id})")

    swap = SwapRequest(
        swap_id=next_id(db, "swap", "SWP", 6, year=requester_assignment.shift.shift_date.year),
        requester_employee_id=requester_assignment.employee_id,
        target_employee_id=target_assignment.employee_id,
        requester_assignment_id=requester_assignment_id,
        target_assignment_id=target_assignment_id,
        reason=reason,
        status=SwapStatus.REQUESTED,
        requester_agreed=True,
        target_agreed=False,
    )
    db.add(swap)
    _history(db, swap, user, None, SwapStatus.REQUESTED, "REQUESTED", reason)
    record_audit(db, user, "REQUEST_SWAP", "SwapRequest", swap.swap_id,
                 new={"requester_assignment_id": requester_assignment_id,
                      "target_assignment_id": target_assignment_id})
    db.commit()
    return get_swap(db, user, swap.swap_id)


def _assert_manager(db: Session, user: User, swap: SwapRequest) -> None:
    role = user.role_value
    if role in {RoleName.ADMIN, RoleName.HR}:
        return
    if role != RoleName.MANAGER:
        raise PermissionDeniedError("Only a manager or HR can approve swaps")
    if user.employee_id in {swap.requester_employee_id, swap.target_employee_id}:
        raise PermissionDeniedError("You cannot approve a swap you are participating in")
    requester = db.get(Employee, swap.requester_employee_id)
    target = db.get(Employee, swap.target_employee_id)
    managed = set(managed_team_ids(db, user))
    if not requester or requester.team_id not in managed or not target or target.team_id not in managed:
        raise PermissionDeniedError("You can only approve swaps within teams you manage")


def respond_as_target(db: Session, user: User, swap_id: str, agree: bool,
                      comment: str | None) -> SwapRequest:
    swap = get_swap(db, user, swap_id)
    if user.employee_id != swap.target_employee_id:
        raise PermissionDeniedError("Only the target employee can respond to this swap")
    if swap.status != SwapStatus.REQUESTED:
        raise ConflictError(f"Cannot respond to a swap in {swap.status.value} state")
    swap.target_agreed = agree
    swap.target_responded_at = utcnow()
    if agree:
        _history(db, swap, user, swap.status, SwapStatus.REQUESTED, "TARGET_ACCEPTED", comment)
    else:
        previous = swap.status
        swap.status = SwapStatus.REJECTED
        swap.decided_at = utcnow()
        _history(db, swap, user, previous, SwapStatus.REJECTED, "TARGET_DECLINED", comment)
    record_audit(db, user, "TARGET_RESPONSE", "SwapRequest", swap.swap_id,
                 new={"target_agreed": agree})
    db.commit()
    return get_swap(db, user, swap.swap_id)


def approve_swap(db: Session, user: User, swap_id: str, comment: str | None,
                  apply_immediately: bool = True) -> SwapRequest:
    swap = get_swap(db, user, swap_id)
    if swap.status != SwapStatus.REQUESTED:
        raise ConflictError(f"Only REQUESTED swaps can be approved (current: {swap.status.value})")
    _assert_manager(db, user, swap)
    if not swap.target_agreed:
        raise ConflictError("The target employee has not agreed to the swap")
    requester_assignment = _assignment(db, swap.requester_assignment_id)
    target_assignment = _assignment(db, swap.target_assignment_id)
    issues = evaluate_swap(db, requester_assignment, target_assignment)
    if issues:
        raise ValidationError("Swap failed validation", details={"issues": issues})
    previous = swap.status
    swap.status = SwapStatus.APPROVED
    swap.manager_user_id = user.user_id
    swap.decided_at = utcnow()
    swap.decision_comment = comment
    _history(db, swap, user, previous, SwapStatus.APPROVED, "APPROVED", comment)
    record_audit(db, user, "APPROVE_SWAP", "SwapRequest", swap.swap_id,
                 previous={"status": previous.value}, new={"status": "APPROVED"})
    db.commit()
    if apply_immediately:
        return apply_swap(db, user, swap_id, comment)
    return get_swap(db, user, swap_id)


def apply_swap(db: Session, user: User, swap_id: str, comment: str | None = None) -> SwapRequest:
    swap = get_swap(db, user, swap_id)
    if swap.status != SwapStatus.APPROVED:
        raise ConflictError(
            "A swap can only be applied after manager approval; "
            f"current state is {swap.status.value}"
        )
    requester_assignment = _assignment(db, swap.requester_assignment_id)
    target_assignment = _assignment(db, swap.target_assignment_id)
    if requester_assignment.shift.shift_date < date.today():
        raise ValidationError("Past shifts cannot be swapped")
    if requester_assignment.status.value != AssignmentStatus.SCHEDULED.value and \
            requester_assignment.status.value != AssignmentStatus.CONFIRMED.value:
        raise ConflictError("Requester assignment is no longer active")
    if target_assignment.status.value != AssignmentStatus.SCHEDULED.value and \
            target_assignment.status.value != AssignmentStatus.CONFIRMED.value:
        raise ConflictError("Target assignment is no longer active")
    issues = evaluate_swap(db, requester_assignment, target_assignment)
    if issues:
        raise ValidationError("Swap failed re-validation at apply time", details={"issues": issues})

    previous_requester = requester_assignment.employee_id
    previous_target = target_assignment.employee_id
    requester_assignment.status = AssignmentStatus.SWAPPED_OUT
    target_assignment.status = AssignmentStatus.SWAPPED_OUT

    new_for_target = AssignmentModel(
        assignment_id=next_id(db, "assignment", "ASG", 6),
        shift_id=requester_assignment.shift_id,
        employee_id=previous_target,
        status=AssignmentStatus.SWAPPED_IN,
        assignment_source=AssignmentSource.SWAP,
        scheduled_hours=requester_assignment.scheduled_hours,
        is_overtime=False,
        notes=f"Created by swap {swap.swap_id}",
    )
    new_for_requester = AssignmentModel(
        assignment_id=next_id(db, "assignment", "ASG", 6),
        shift_id=target_assignment.shift_id,
        employee_id=previous_requester,
        status=AssignmentStatus.SWAPPED_IN,
        assignment_source=AssignmentSource.SWAP,
        scheduled_hours=target_assignment.scheduled_hours,
        is_overtime=False,
        notes=f"Created by swap {swap.swap_id}",
    )
    db.add_all([new_for_target, new_for_requester])
    swap.status = SwapStatus.APPLIED
    swap.applied_at = utcnow()
    _history(db, swap, user, SwapStatus.APPROVED, SwapStatus.APPLIED, "APPLIED", comment)
    record_audit(db, user, "APPLY_SWAP", "SwapRequest", swap.swap_id,
                 previous={"status": "APPROVED", "requester_assignment": requester_assignment.assignment_id,
                           "target_assignment": target_assignment.assignment_id},
                 new={"status": "APPLIED", "new_assignments": [new_for_target.assignment_id,
                                                                new_for_requester.assignment_id]})
    db.commit()
    return get_swap(db, user, swap_id)


def reject_swap(db: Session, user: User, swap_id: str, comment: str | None) -> SwapRequest:
    swap = get_swap(db, user, swap_id)
    if swap.status not in {SwapStatus.REQUESTED, SwapStatus.APPROVED}:
        raise ConflictError(f"Cannot reject a swap in {swap.status.value} state")
    if swap.status == SwapStatus.REQUESTED:
        if user.employee_id == swap.target_employee_id:
            pass
        else:
            _assert_manager(db, user, swap)
    else:
        _assert_manager(db, user, swap)
    if not comment:
        raise ValidationError("A rejection comment is required")
    previous = swap.status
    swap.status = SwapStatus.REJECTED
    swap.manager_user_id = user.user_id
    swap.decided_at = utcnow()
    swap.decision_comment = comment
    _history(db, swap, user, previous, SwapStatus.REJECTED, "REJECTED", comment)
    record_audit(db, user, "REJECT_SWAP", "SwapRequest", swap.swap_id,
                 previous={"status": previous.value}, new={"status": "REJECTED"})
    db.commit()
    return get_swap(db, user, swap_id)


def cancel_swap(db: Session, user: User, swap_id: str, comment: str | None = None) -> SwapRequest:
    swap = get_swap(db, user, swap_id)
    if swap.status != SwapStatus.REQUESTED:
        raise ConflictError("Only REQUESTED swaps can be cancelled")
    if user.employee_id != swap.requester_employee_id and user.role_value not in {
        RoleName.HR, RoleName.ADMIN
    }:
        raise PermissionDeniedError("Only the requester or HR can cancel this swap")
    previous = swap.status
    swap.status = SwapStatus.CANCELLED
    _history(db, swap, user, previous, SwapStatus.CANCELLED, "CANCELLED", comment)
    record_audit(db, user, "CANCEL_SWAP", "SwapRequest", swap.swap_id,
                 previous={"status": previous.value}, new={"status": "CANCELLED"})
    db.commit()
    return get_swap(db, user, swap_id)
