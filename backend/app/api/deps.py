"""FastAPI dependencies: database, authentication, authorisation, scoping."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import date
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import PermissionDeniedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.auth import User
from app.models.enums import RoleName
from app.models.master import Employee, TeamManager

bearer_scheme = HTTPBearer(auto_error=False)


def db_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(db_session),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def require_roles(*roles: RoleName | str) -> Callable:
    allowed = {r.value if isinstance(r, RoleName) else str(r) for r in roles}
    allowed.add(RoleName.ADMIN.value)

    def dependency(user: User = Depends(get_current_user)) -> User:
        role = user.role.name.value if user.role else None
        if role not in allowed:
            raise PermissionDeniedError(
                f"Role {role} is not permitted to perform this action"
            )
        return user

    return dependency


def admin_user(user: User = Depends(require_roles(RoleName.ADMIN))) -> User:
    return user


def manager_or_above(user: User = Depends(require_roles(RoleName.MANAGER, RoleName.HR))) -> User:
    return user


def hr_or_above(user: User = Depends(require_roles(RoleName.HR))) -> User:
    return user


def get_current_employee(
    user: User = Depends(get_current_user), db: Session = Depends(db_session)
) -> Employee:
    if not user.employee_id:
        raise HTTPException(status_code=400, detail="User is not linked to an employee record")
    employee = db.get(Employee, user.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee record not found")
    return employee


def managed_team_ids(db: Session, user: User) -> list[str]:
    if not user.employee_id:
        return []
    today = date.today()
    rows = db.execute(
        select(TeamManager.team_id).where(
            TeamManager.employee_id == user.employee_id,
            TeamManager.effective_from <= today,
            (TeamManager.effective_to.is_(None)) | (TeamManager.effective_to >= today),
        )
    ).scalars().all()
    return list(rows)


def can_access_team(db: Session, user: User, team_id: str) -> bool:
    role = user.role.name.value if user.role else None
    if role in {RoleName.ADMIN.value, RoleName.HR.value}:
        return True
    if role == RoleName.MANAGER.value:
        return team_id in managed_team_ids(db, user)
    if role == RoleName.EMPLOYEE.value and user.employee_id:
        employee = db.get(Employee, user.employee_id)
        return bool(employee and employee.team_id == team_id)
    return False


def ensure_team_access(db: Session, user: User, team_id: str) -> None:
    if not can_access_team(db, user, team_id):
        raise PermissionDeniedError("You do not have access to this team's data")


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def pagination(page: int = 1, page_size: int = 25) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    return {"page": page, "page_size": page_size, "offset": (page - 1) * page_size}
