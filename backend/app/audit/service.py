"""Append-only audit trail helper."""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.auth import User


def record_audit(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    *,
    previous: Any = None,
    new: Any = None,
    reason: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_user_id=actor.user_id if actor else None,
        actor_role=actor.role.name.value if actor and actor.role else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        previous_state=jsonable_encoder(previous) if previous is not None else None,
        new_state=jsonable_encoder(new) if new is not None else None,
        reason=reason,
        ip_address=ip_address,
    )
    db.add(log)
    return log
