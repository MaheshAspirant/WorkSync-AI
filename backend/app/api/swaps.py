"""Shift-swap endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_current_user, require_roles
from app.models.auth import User
from app.models.enums import RoleName, SwapStatus
from app.schemas.common import Page
from app.schemas.employees import AssignmentOut
from app.schemas.swap import (
    SwapActionRequest,
    SwapCreate,
    SwapOut,
    SwapTargetResponse,
)
from app.services import swap_service

router = APIRouter(prefix="/swaps", tags=["Shift Swaps"])


@router.get("", response_model=Page[SwapOut])
def list_swaps(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    status_filter: SwapStatus | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    rows, total = swap_service.list_swaps(
        db, user, page=page, page_size=page_size, status=status_filter
    )
    return Page.build(rows, total, page, page_size)


@router.post("", response_model=SwapOut, status_code=status.HTTP_201_CREATED)
def create_swap(
    payload: SwapCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    return swap_service.create_swap(
        db, user, payload.requester_assignment_id, payload.target_assignment_id, payload.reason
    )


@router.get("/candidates", response_model=list[AssignmentOut])
def swap_candidates(
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    from datetime import timedelta

    today = date.today()
    start = start or today
    end = end or (today + timedelta(days=90))
    return swap_service.swap_candidates(db, user, start, end)


@router.get("/{swap_id}", response_model=SwapOut)
def get_swap(
    swap_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    return swap_service.get_swap(db, user, swap_id)


@router.put("/{swap_id}/target-response", response_model=SwapOut)
def target_response(
    swap_id: str,
    payload: SwapTargetResponse,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    return swap_service.respond_as_target(db, user, swap_id, payload.agree, payload.comment)


@router.put("/{swap_id}/approve", response_model=SwapOut)
def approve_swap(
    swap_id: str,
    payload: SwapActionRequest,
    apply_immediately: bool = Query(True),
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    return swap_service.approve_swap(
        db, user, swap_id, payload.comment, apply_immediately=apply_immediately
    )


@router.put("/{swap_id}/apply", response_model=SwapOut)
def apply_swap(
    swap_id: str,
    payload: SwapActionRequest | None = None,
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    return swap_service.apply_swap(db, user, swap_id, payload.comment if payload else None)


@router.put("/{swap_id}/reject", response_model=SwapOut)
def reject_swap(
    swap_id: str,
    payload: SwapActionRequest,
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    return swap_service.reject_swap(db, user, swap_id, payload.comment)


@router.put("/{swap_id}/cancel", response_model=SwapOut)
def cancel_swap(
    swap_id: str,
    payload: SwapActionRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    return swap_service.cancel_swap(db, user, swap_id, payload.comment if payload else None)
