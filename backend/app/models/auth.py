"""Authentication and role models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import RoleName
from app.models.master import enum_col

if TYPE_CHECKING:
    from app.models.master import Employee


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    role_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[RoleName] = mapped_column(enum_col(RoleName, 30), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    permissions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.employee_id"), unique=True, nullable=True, index=True
    )
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.role_id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    role: Mapped["Role"] = relationship(back_populates="users", lazy="joined")
    employee: Mapped["Employee | None"] = relationship(lazy="joined")

    @property
    def role_value(self) -> RoleName:
        return self.role.name if self.role else RoleName.EMPLOYEE
