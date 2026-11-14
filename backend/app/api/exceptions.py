"""Conflict / exception management endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_current_user, require_roles
from app.core.errors import PermissionDeniedError
from app.models.auth import User
from app.models.enums import IssueType, ResolutionStatus, RoleName, Severity
from app.schemas.common import Page
from app.schemas.scheduling import (
    DetectionSummary,
    ExceptionOut,
    ResolveExceptionRequest,
)
from app.services import conflict_service

router = APIRouter(prefix="/exceptions", tags=["Conflicts & Exceptions"])


@router.get("", response_model=Page[ExceptionOut])
def list_exceptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    issue_type: IssueType | None = None,
    resolution_status: ResolutionStatus | None = None,
    severity: Severity | None = None,
    run_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    rows, total = conflict_service.list_exceptions(
        db, user, page=page, page_size=page_size, issue_type=issue_type,
        status=resolution_status, severity=severity, run_id=run_id,
    )
    return Page.build(rows, total, page, page_size)


@router.post("/detect", response_model=DetectionSummary)
def detect_exceptions(
    start: date | None = None,
    end: date | None = None,
    include_attendance: bool = False,
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    drafts = conflict_service.detect_issues(
        db, start=start, end=end, include_attendance=include_attendance
    )
    return conflict_service.persist_issues(db, user, drafts)


@router.get("/summary")
def exception_summary(
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    by_type = [
        {"issue_type": issue_type.value, "count": count}
        for issue_type, count in db.execute(
            select(
                conflict_service.SchedulingException.issue_type,
                func.count(),
            ).group_by(conflict_service.SchedulingException.issue_type)
        ).all()
    ]
    by_status = [
        {"resolution_status": status.value, "count": count}
        for status, count in db.execute(
            select(
                conflict_service.SchedulingException.resolution_status,
                func.count(),
            ).group_by(conflict_service.SchedulingException.resolution_status)
        ).all()
    ]
    return {"by_type": by_type, "by_status": by_status}


@router.get("/{issue_id}", response_model=ExceptionOut)
def get_exception(
    issue_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    issue = conflict_service.get_exception(db, issue_id)
    role = user.role_value
    if role == RoleName.EMPLOYEE and issue.employee_id != user.employee_id:
        raise PermissionDeniedError("You can only view your own exceptions")
    if role == RoleName.MANAGER:
        from app.api.deps import managed_team_ids
        from app.models.master import Employee, Shift

        teams = set(managed_team_ids(db, user))
        employee_team = (
            db.get(Employee, issue.employee_id).team_id if issue.employee_id else None
        )
        shift_team = db.get(Shift, issue.shift_id).team_id if issue.shift_id else None
        if employee_team not in teams and shift_team not in teams:
            raise PermissionDeniedError("You can only view exceptions for your teams")
    return issue


@router.put("/{issue_id}/resolve", response_model=ExceptionOut)
def resolve_exception(
    issue_id: str,
    payload: ResolveExceptionRequest,
    user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR)),
    db: Session = Depends(db_session),
):
    return conflict_service.resolve_exception(
        db, user, issue_id, payload.resolution_status, payload.note
    )
