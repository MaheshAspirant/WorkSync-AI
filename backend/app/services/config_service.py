"""Runtime system configuration persisted in the database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import SystemConfig

DEFAULTS: dict[str, object] = {
    "standard_weekly_hours": 40.0,
    "standard_daily_hours": 8.0,
    "default_overtime_cap_weekly": 10.0,
    "default_min_rest_hours": 11.0,
    "scheduler_time_limit_seconds": 12.0,
    "leave_approval_required": True,
    "swap_target_agreement_required": True,
    "swap_manager_approval_required": True,
    "attendance_late_grace_minutes": 5,
    "attendance_absence_grace_minutes": 30,
}


def get_setting(db: Session, key: str, default=None):
    if default is None:
        default = DEFAULTS.get(key)
    row = db.get(SystemConfig, key)
    if row is None or row.config_value is None:
        return default
    return row.config_value


def set_setting(db: Session, key: str, value, description: str | None = None,
                updated_by_user_id: str | None = None) -> SystemConfig:
    row = db.get(SystemConfig, key)
    if row is None:
        row = SystemConfig(
            config_key=key,
            config_value=value,
            description=description or f"Runtime setting {key}",
            updated_by_user_id=updated_by_user_id,
        )
        db.add(row)
    else:
        row.config_value = value
        if description:
            row.description = description
        row.updated_by_user_id = updated_by_user_id
    return row


def list_settings(db: Session) -> list[SystemConfig]:
    return list(db.execute(select(SystemConfig).order_by(SystemConfig.config_key)).scalars())


def ensure_defaults(db: Session) -> None:
    for key, value in DEFAULTS.items():
        if db.get(SystemConfig, key) is None:
            set_setting(db, key, value)
    db.flush()
