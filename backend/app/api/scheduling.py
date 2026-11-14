"""Automated scheduling, shift and assignment endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_current_user, require_roles
from app.models.auth import User
from app.models.enums import RoleName, RunStatus
from app.schemas.common import Page
from app.schemas.employees import AssignmentOut, ShiftOut
from app.schemas.scheduling import (
    GenerateScheduleRequest,
    SchedulingRunOut,
    SchedulingRunSummary,
)
from app.services import scheduling_service

router = APIRouter(prefix="/scheduling", tags=["Scheduling"])


@router.post("/generate", response_model=SchedulingRunOut, status_code=status.HTTP_201_CREATED)
def generate_schedule(
    payload: GenerateScheduleRequest,
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    return scheduling_service.generate_schedule(db, user, payload)


@router.get("/runs", response_model=Page[SchedulingRunSummary])
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: RunStatus | None = Query(None, alias="status"),
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    rows, total = scheduling_service.list_runs(
        db, user, page=page, page_size=page_size, status=status_filter
    )
    return Page.build(rows, total, page, page_size)


@router.get("/runs/{run_id}", response_model=SchedulingRunOut)
def get_run(
    run_id: str,
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    return scheduling_service.get_run(db, user, run_id)


@router.get("/assignments", response_model=Page[AssignmentOut])
def list_assignments(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    team_id: str | None = None,
    employee_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    rows, total = scheduling_service.list_assignments(
        db, user, page=page, page_size=page_size, team_id=team_id,
        employee_id=employee_id, start=start, end=end,
    )
    return Page.build(rows, total, page, page_size)


@router.get("/shifts", response_model=Page[ShiftOut])
def list_shifts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    team_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    rows, total = scheduling_service.list_shifts(
        db, user, page=page, page_size=page_size, team_id=team_id, start=start, end=end
    )
    return Page.build(rows, total, page, page_size)
