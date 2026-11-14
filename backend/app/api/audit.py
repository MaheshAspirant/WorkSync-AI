"""Audit-trail endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_roles
from app.models.audit import AuditLog
from app.models.enums import RoleName
from app.schemas.audit import AuditLogOut
from app.schemas.common import Page

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=Page[AuditLogOut])
def list_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_user_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    _user=Depends(require_roles(RoleName.HR)),
    db: Session = Depends(db_session),
):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if start:
        stmt = stmt.where(func.date(AuditLog.created_at) >= start)
    if end:
        stmt = stmt.where(func.date(AuditLog.created_at) <= end)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars()
    )
    return Page.build(rows, total, page, page_size)
