"""Leave lifecycle: PENDING -> APPROVED / REJECTED / CANCELLED."""

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
from app.db.base import utcnow
from app.models.auth import User
from app.models.enums import LeaveStatus, LeaveType, RoleName
from app.models.leave import LeaveApprovalHistory, LeaveRequest
from app.models.master import Employee, HolidayCalendar, LeavePolicy
from app.schemas.leave import LeaveCreate


def _visible_leave_stmt(db: Session, user: User):
    stmt = select(LeaveRequest).options(
        joinedload(LeaveRequest.employee),
        joinedload(LeaveRequest.policy),
        joinedload(LeaveRequest.approvals),
    )
    role = user.role_value
    if role in {RoleName.ADMIN, RoleName.HR}:
        return stmt
    if role == RoleName.MANAGER:
        teams = managed_team_ids(db, user)
        if not teams:
            return stmt.where(LeaveRequest.employee_id == (user.employee_id or "__none__"))
        return stmt.join(Employee, Employee.employee_id == LeaveRequest.employee_id).where(
            Employee.team_id.in_(teams)
        )
    return stmt.where(LeaveRequest.employee_id == (user.employee_id or "__none__"))


def list_leaves(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 25,
    status: LeaveStatus | None = None,
    leave_type: LeaveType | None = None,
    employee_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> tuple[list[LeaveRequest], int]:
    stmt = _visible_leave_stmt(db, user)
    if status:
        stmt = stmt.where(LeaveRequest.status == status)
    if leave_type:
        stmt = stmt.where(LeaveRequest.leave_type == leave_type)
    if employee_id:
        stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    if start:
        stmt = stmt.where(LeaveRequest.end_date >= start)
    if end:
        stmt = stmt.where(LeaveRequest.start_date <= end)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(LeaveRequest.submitted_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().scalars()
    )
    return rows, total


def get_leave(db: Session, user: User, leave_id: str) -> LeaveRequest:
    leave = db.execute(
        _visible_leave_stmt(db, user).where(LeaveRequest.leave_id == leave_id)
    ).unique().scalar_one_or_none()
    if leave is None:
        raise NotFoundError("Leave request not found")
    return leave


def _holiday_dates(db: Session, start: date, end: date) -> set[date]:
    rows = db.execute(
        select(HolidayCalendar.holiday_date).where(
            HolidayCalendar.holiday_date >= start, HolidayCalendar.holiday_date <= end
        )
    ).scalars()
    return set(rows)


def working_days(db: Session, start: date, end: date) -> float:
    holidays = _holiday_dates(db, start, end)
    count = 0
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5 and cursor not in holidays:
            count += 1
        cursor += timedelta(days=1)
    return float(count)


def _policy_for(db: Session, leave_type: LeaveType) -> LeavePolicy:
    policy = db.execute(
        select(LeavePolicy).where(LeavePolicy.leave_type == leave_type.value)
    ).scalar_one_or_none()
    if policy is None:
        raise ValidationError(f"No leave policy configured for {leave_type.value}")
    return policy


def _assert_can_file_for(db: Session, user: User, employee: Employee) -> None:
    role = user.role_value
    if role in {RoleName.ADMIN, RoleName.HR}:
        return
    if role == RoleName.MANAGER and employee.team_id in managed_team_ids(db, user):
        return
    if role == RoleName.EMPLOYEE and user.employee_id == employee.employee_id:
        return
    raise PermissionDeniedError("You cannot file leave for this employee")


def _assert_can_decide(db: Session, user: User, leave: LeaveRequest) -> None:
    role = user.role_value
    if role in {RoleName.ADMIN, RoleName.HR}:
        if user.employee_id == leave.employee_id:
            raise PermissionDeniedError("You cannot approve your own leave request")
        return
    if role != RoleName.MANAGER:
        raise PermissionDeniedError("Only managers or HR can decide leave requests")
    if leave.employee.team_id not in managed_team_ids(db, user):
        raise PermissionDeniedError("You can only decide leave for your own team")
    if user.employee_id == leave.employee_id:
        raise PermissionDeniedError("You cannot approve your own leave request")


def create_leave(db: Session, user: User, payload: LeaveCreate) -> LeaveRequest:
    employee_id = payload.employee_id or user.employee_id
    if not employee_id:
        raise ValidationError("employee_id is required for users not linked to an employee")
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise NotFoundError("Employee not found")
    if employee.status.value != "ACTIVE":
        raise ValidationError("Leave can only be requested for active employees")
    _assert_can_file_for(db, user, employee)
    if payload.end_date < payload.start_date:
        raise ValidationError("end_date must be on or after start_date")
    if payload.start_date < date.today() - timedelta(days=365):
        raise ValidationError("Leave cannot be requested more than one year in the past")
    policy = _policy_for(db, payload.leave_type)
    days = working_days(db, payload.start_date, payload.end_date)
    if days <= 0:
        raise ValidationError("The selected range contains no working days")
    calendar_days = (payload.end_date - payload.start_date).days + 1
    if calendar_days > policy.max_consecutive_days:
        raise ValidationError(
            f"{payload.leave_type.value} leave cannot exceed {policy.max_consecutive_days} consecutive days"
        )
    if policy.min_notice_days and payload.start_date < date.today() + timedelta(days=policy.min_notice_days):
        # Historical/bulk data and sick leave are exempt from the forward-looking notice rule.
        if payload.leave_type != LeaveType.SICK and payload.start_date >= date.today():
            raise ValidationError(
                f"{payload.leave_type.value} leave requires {policy.min_notice_days} days notice"
            )
    overlapping = db.execute(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            LeaveRequest.start_date <= payload.end_date,
            LeaveRequest.end_date >= payload.start_date,
        )
    ).scalars().first()
    if overlapping:
        raise ConflictError(
            f"Overlaps existing {overlapping.status.value.lower()} leave {overlapping.leave_id}"
        )
    if payload.leave_type == LeaveType.ANNUAL:
        used = db.execute(
            select(func.coalesce(func.sum(LeaveRequest.total_days), 0.0)).where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.leave_type == LeaveType.ANNUAL,
                LeaveRequest.status.in_([LeaveStatus.APPROVED, LeaveStatus.PENDING]),
                LeaveRequest.start_date >= date(payload.start_date.year, 1, 1),
                LeaveRequest.start_date <= date(payload.start_date.year, 12, 31),
            )
        ).scalar_one()
        if float(used) + days > policy.annual_entitlement_days:
            raise ValidationError(
                f"Insufficient annual leave balance: {policy.annual_entitlement_days - float(used):.1f} days remaining"
            )
    leave = LeaveRequest(
        leave_id=next_id(db, "leave", "LVE", 6, year=payload.start_date.year),
        employee_id=employee_id,
        policy_id=policy.policy_id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_days=days,
        reason=payload.reason,
        status=LeaveStatus.PENDING,
        submitted_at=utcnow(),
    )
    db.add(leave)
    db.add(
        LeaveApprovalHistory(
            leave_id=leave.leave_id,
            from_status=None,
            to_status=LeaveStatus.PENDING,
            action="SUBMITTED",
            actor_user_id=user.user_id,
            comment=payload.reason,
        )
    )
    record_audit(db, user, "SUBMIT_LEAVE", "LeaveRequest", leave.leave_id,
                 new={"employee_id": employee_id, "start_date": str(payload.start_date),
                      "end_date": str(payload.end_date), "days": days,
                      "type": payload.leave_type.value})
    db.commit()
    return get_leave(db, user, leave.leave_id)


def _transition(db: Session, user: User, leave: LeaveRequest, to_status: LeaveStatus,
                action: str, comment: str | None) -> LeaveRequest:
    previous = leave.status
    leave.status = to_status
    leave.decided_at = utcnow()
    leave.decided_by_user_id = user.user_id
    leave.manager_comment = comment
    history = LeaveApprovalHistory(
        leave_id=leave.leave_id,
        from_status=previous,
        to_status=to_status,
        action=action,
        actor_user_id=user.user_id,
        comment=comment,
    )
    # Keep the already-loaded relationship in sync so the response contains the
    # new lifecycle event immediately (expire_on_commit is disabled).
    leave.approvals.append(history)
    record_audit(db, user, action, "LeaveRequest", leave.leave_id,
                 previous={"status": previous.value}, new={"status": to_status.value},
                 reason=comment)
    db.commit()
    return get_leave(db, user, leave.leave_id)


def approve_leave(db: Session, user: User, leave_id: str, comment: str | None) -> LeaveRequest:
    leave = get_leave(db, user, leave_id)
    if leave.status != LeaveStatus.PENDING:
        raise ConflictError(f"Only PENDING leave can be approved (current: {leave.status.value})")
    _assert_can_decide(db, user, leave)
    return _transition(db, user, leave, LeaveStatus.APPROVED, "APPROVED", comment)


def reject_leave(db: Session, user: User, leave_id: str, comment: str | None) -> LeaveRequest:
    leave = get_leave(db, user, leave_id)
    if leave.status != LeaveStatus.PENDING:
        raise ConflictError(f"Only PENDING leave can be rejected (current: {leave.status.value})")
    _assert_can_decide(db, user, leave)
    if not comment:
        raise ValidationError("A rejection comment is required")
    return _transition(db, user, leave, LeaveStatus.REJECTED, "REJECTED", comment)


def cancel_leave(db: Session, user: User, leave_id: str, comment: str | None = None) -> LeaveRequest:
    leave = get_leave(db, user, leave_id)
    role = user.role_value
    if role == RoleName.EMPLOYEE and user.employee_id != leave.employee_id:
        raise PermissionDeniedError("You can only cancel your own leave")
    if leave.status not in {LeaveStatus.PENDING, LeaveStatus.APPROVED}:
        raise ConflictError(f"Cannot cancel leave in {leave.status.value} state")
    if leave.status == LeaveStatus.APPROVED and role not in {RoleName.HR, RoleName.ADMIN}:
        raise PermissionDeniedError("Only HR/Admin can cancel approved leave")
    return _transition(db, user, leave, LeaveStatus.CANCELLED, "CANCELLED", comment)


def leave_balances(db: Session, employee_id: str, year: int) -> list[dict]:
    if db.get(Employee, employee_id) is None:
        raise NotFoundError("Employee not found")
    policies = list(db.execute(select(LeavePolicy).order_by(LeavePolicy.policy_id)).scalars())
    result = []
    for policy in policies:
        approved = db.execute(
            select(func.coalesce(func.sum(LeaveRequest.total_days), 0.0)).where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.policy_id == policy.policy_id,
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.start_date >= date(year, 1, 1),
            )
        ).scalar_one()
        pending = db.execute(
            select(func.coalesce(func.sum(LeaveRequest.total_days), 0.0)).where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.policy_id == policy.policy_id,
                LeaveRequest.status == LeaveStatus.PENDING,
                LeaveRequest.start_date >= date(year, 1, 1),
            )
        ).scalar_one()
        result.append(
            {
                "leave_type": policy.leave_type,
                "entitlement_days": policy.annual_entitlement_days,
                "approved_days": float(approved),
                "pending_days": float(pending),
                "remaining_days": max(
                    0.0, policy.annual_entitlement_days - float(approved) - float(pending)
                ),
            }
        )
    return result
