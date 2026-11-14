"""Authentication and user administration."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from app.core.ids import next_id
from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import utcnow
from app.models.auth import Role, User
from app.models.enums import RoleName
from app.models.master import Employee


def serialize_user(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "role": user.role_value,
        "employee_id": user.employee_id,
        "is_active": user.is_active,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    }


def authenticate(db: Session, username: str, password: str, ip: str | None = None) -> User:
    user = db.execute(
        select(User).where(or_(User.username == username, User.email == username))
    ).scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        # Deliberately identical message: do not reveal whether the account exists.
        raise BusinessRuleError("Invalid username or password", status_code=401,
                                code="INVALID_CREDENTIALS")
    if not user.is_active:
        raise BusinessRuleError("This account is disabled", status_code=403, code="ACCOUNT_DISABLED")
    previous = {"last_login_at": user.last_login_at.isoformat() if user.last_login_at else None}
    user.last_login_at = utcnow()
    record_audit(db, user, "LOGIN", "User", user.user_id, previous=previous,
                 new={"last_login_at": user.last_login_at.isoformat()}, ip_address=ip)
    db.commit()
    return user


def issue_token(user: User) -> tuple[str, int]:
    return create_access_token(user.user_id, user.role_value.value, {"username": user.username})


def register_employee_user(db: Session, username: str, email: str, password: str,
                           employee_id: str | None = None, actor: User | None = None) -> User:
    if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        raise ConflictError("Username already exists")
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise ConflictError("Email already registered")
    if employee_id:
        employee = db.get(Employee, employee_id)
        if employee is None:
            raise NotFoundError("Employee not found")
        if employee.status.value != "ACTIVE":
            raise ValidationError("Cannot create a login for an inactive employee")
        if db.execute(select(User).where(User.employee_id == employee_id)).scalar_one_or_none():
            raise ConflictError("Employee already has a user account")
    role = db.execute(select(Role).where(Role.name == RoleName.EMPLOYEE)).scalar_one()
    user = User(
        user_id=next_id(db, "user", "USR", 6),
        username=username,
        email=email,
        password_hash=hash_password(password),
        role_id=role.role_id,
        employee_id=employee_id,
        is_active=True,
    )
    db.add(user)
    record_audit(db, actor, "REGISTER_USER", "User", user.user_id,
                 new={"username": username, "role": RoleName.EMPLOYEE.value,
                      "employee_id": employee_id})
    db.commit()
    db.refresh(user)
    return user


def admin_create_user(db: Session, actor: User, username: str, email: str, password: str,
                      role: RoleName, employee_id: str | None = None) -> User:
    if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        raise ConflictError("Username already exists")
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise ConflictError("Email already registered")
    role_row = db.execute(select(Role).where(Role.name == role)).scalar_one_or_none()
    if role_row is None:
        raise ValidationError(f"Unknown role {role}")
    if employee_id:
        if db.get(Employee, employee_id) is None:
            raise NotFoundError("Employee not found")
        if db.execute(select(User).where(User.employee_id == employee_id)).scalar_one_or_none():
            raise ConflictError("Employee already has a user account")
    user = User(
        user_id=next_id(db, "user", "USR", 6),
        username=username,
        email=email,
        password_hash=hash_password(password),
        role_id=role_row.role_id,
        employee_id=employee_id,
        is_active=True,
    )
    db.add(user)
    record_audit(db, actor, "CREATE_USER", "User", user.user_id,
                 new={"username": username, "role": role.value, "employee_id": employee_id})
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, actor: User, user_id: str, **changes) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    previous = serialize_user(user)
    if "email" in changes and changes["email"]:
        existing = db.execute(select(User).where(User.email == changes["email"])).scalar_one_or_none()
        if existing and existing.user_id != user_id:
            raise ConflictError("Email already registered")
        user.email = changes["email"]
    if changes.get("role"):
        role_row = db.execute(select(Role).where(Role.name == changes["role"])).scalar_one_or_none()
        if role_row is None:
            raise ValidationError("Unknown role")
        user.role_id = role_row.role_id
    if changes.get("is_active") is not None:
        if user_id == actor.user_id and not changes["is_active"]:
            raise ValidationError("You cannot deactivate your own account")
        user.is_active = changes["is_active"]
    if changes.get("password"):
        user.password_hash = hash_password(changes["password"])
    record_audit(db, actor, "UPDATE_USER", "User", user_id, previous=previous,
                 new=serialize_user(user))
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise BusinessRuleError("Current password is incorrect", status_code=400,
                                code="INVALID_PASSWORD")
    user.password_hash = hash_password(new_password)
    record_audit(db, user, "CHANGE_PASSWORD", "User", user.user_id)
    db.commit()


def list_users(db: Session, page: int, page_size: int, q: str | None = None,
               role: RoleName | None = None) -> tuple[list[User], int]:
    stmt = select(User)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.email.ilike(like)))
    if role:
        stmt = stmt.join(Role).where(Role.name == role)
    total = len(db.execute(stmt).scalars().all())
    users = list(
        db.execute(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size)
                   .limit(page_size)).scalars()
    )
    return users, total


def list_roles(db: Session) -> list[Role]:
    return list(db.execute(select(Role).order_by(Role.role_id)).scalars())
