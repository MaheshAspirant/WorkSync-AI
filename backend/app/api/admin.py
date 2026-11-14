"""System administration: users, roles, configuration and validation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_roles
from app.models.auth import User
from app.models.enums import RoleName
from app.schemas.audit import (
    SystemConfigOut,
    SystemConfigUpdate,
    ValidationReport,
)
from app.schemas.auth import RoleOut, UserCreateRequest, UserOut, UserUpdateRequest
from app.schemas.common import Message, Page
from app.services import auth_service, config_service, validation_service

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/users", response_model=Page[UserOut])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str | None = None,
    role: RoleName | None = None,
    user: User = Depends(require_roles(RoleName.ADMIN)),
    db: Session = Depends(db_session),
):
    rows, total = auth_service.list_users(db, page, page_size, q, role)
    return Page.build([auth_service.serialize_user(u) for u in rows], total, page, page_size)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    user: User = Depends(require_roles(RoleName.ADMIN)),
    db: Session = Depends(db_session),
):
    created = auth_service.admin_create_user(
        db, user, payload.username, payload.email, payload.password, payload.role, payload.employee_id
    )
    return auth_service.serialize_user(created)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    user: User = Depends(require_roles(RoleName.ADMIN)),
    db: Session = Depends(db_session),
):
    updated = auth_service.update_user(
        db, user, user_id,
        email=payload.email, role=payload.role, is_active=payload.is_active,
        password=payload.password,
    )
    return auth_service.serialize_user(updated)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    user: User = Depends(require_roles(RoleName.ADMIN)),
    db: Session = Depends(db_session),
):
    return auth_service.list_roles(db)


@router.get("/config", response_model=list[SystemConfigOut])
def list_config(
    user: User = Depends(require_roles(RoleName.ADMIN)),
    db: Session = Depends(db_session),
):
    return config_service.list_settings(db)


@router.put("/config/{key}", response_model=SystemConfigOut)
def update_config(
    key: str,
    payload: SystemConfigUpdate,
    user: User = Depends(require_roles(RoleName.ADMIN)),
    db: Session = Depends(db_session),
):
    row = config_service.set_setting(
        db, key, payload.config_value, payload.description, updated_by_user_id=user.user_id
    )
    from app.audit.service import record_audit
    record_audit(db, user, "UPDATE_CONFIG", "SystemConfig", key,
                 new={"config_value": payload.config_value})
    db.commit()
    db.refresh(row)
    return row


@router.get("/validation", response_model=ValidationReport)
def validation_report(
    user: User = Depends(require_roles(RoleName.ADMIN, RoleName.HR)),
    db: Session = Depends(db_session),
):
    return validation_service.run_validation(db)
