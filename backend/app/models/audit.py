"""Audit trail, system configuration and ID counter models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.auth import User


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.user_id"), nullable=True, index=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), index=True)
    previous_state: Mapped[dict | None] = mapped_column(JSON)
    new_state: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    actor: Mapped["User | None"] = relationship()


class SystemConfig(Base):
    __tablename__ = "system_config"

    config_key: Mapped[str] = mapped_column(String(60), primary_key=True)
    config_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(String(255))
    updated_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class IdCounter(Base):
    """Transactional, zero-padded identifier sequence (per entity prefix)."""

    __tablename__ = "id_counters"

    counter_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
