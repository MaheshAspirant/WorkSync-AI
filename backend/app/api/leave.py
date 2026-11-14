"""Leave management endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_current_user, require_roles
from app.models.auth import User
from app.models.enums import LeaveStatus, LeaveType, RoleName
from app.models.master import Employee, LeavePolicy
from app.schemas.common import Page
from app.schemas.leave import (
    LeaveBalanceResponse,
    LeaveCreate,
    LeaveDecisionRequest,
    LeaveOut,
    LeavePolicyOut,
)
from app.services import leave_service

router = APIRouter(tags=["Leave Management"])


@router.get("/leave-policies", response_model=list[LeavePolicyOut])
def list_policies(user: User = Depends(get_current_user), db: Session = Depends(db_session)):
    return list(db.execute(select(LeavePolicy).order_by(LeavePolicy.policy_id)).scalars())


@router.get("/leaves", response_model=Page[LeaveOut])
def list_leaves(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    status_filter: LeaveStatus | None = Query(None, alias="status"),
    leave_type: LeaveType | None = None,
    employee_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    rows, total = leave_service.list_leaves(
        db, user, page=page, page_size=page_size, status=status_filter,
        leave_type=leave_type, employee_id=employee_id, start=start, end=end,
    )
    return Page.build(rows, total, page, page_size)


@router.post("/leaves", response_model=LeaveOut, status_code=status.HTTP_201_CREATED)
def create_leave(
    payload: LeaveCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    return leave_service.create_leave(db, user, payload)


@router.get("/leaves/balance/{employee_id}", response_model=LeaveBalanceResponse)
def leave_balance(
    employee_id: str,
    year: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    employee = db.get(Employee, employee_id)
    if employee is None:
        from app.core.errors import NotFoundError
        raise NotFoundError("Employee not found")
    from app.services.employee_service import assert_employee_access
    assert_employee_access(db, user, employee)
    target_year = year or date.today().year
    return {
        "employee_id": employee_id,
        "year": target_year,
        "balances": leave_service.leave_balances(db, employee_id, target_year),
    }


@router.get("/leaves/{leave_id}", response_model=LeaveOut)
def get_leave(
    leave_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    return leave_service.get_leave(db, user, leave_id)


@router.put("/leaves/{leave_id}/approve", response_model=LeaveOut)
def approve_leave(
    leave_id: str,
    payload: LeaveDecisionRequest,
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    return leave_service.approve_leave(db, user, leave_id, payload.comment)


@router.put("/leaves/{leave_id}/reject", response_model=LeaveOut)
def reject_leave(
    leave_id: str,
    payload: LeaveDecisionRequest,
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    return leave_service.reject_leave(db, user, leave_id, payload.comment)


@router.put("/leaves/{leave_id}/cancel", response_model=LeaveOut)
def cancel_leave(
    leave_id: str,
    payload: LeaveDecisionRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    return leave_service.cancel_leave(db, user, leave_id, payload.comment if payload else None)
