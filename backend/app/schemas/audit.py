"""Audit and administration schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: int
    actor_user_id: str | None = None
    actor_role: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    previous_state: dict | None = None
    new_state: dict | None = None
    reason: str | None = None
    ip_address: str | None = None
    created_at: datetime


class SystemConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_key: str
    config_value: object | None = None
    description: str | None = None
    updated_by_user_id: str | None = None
    updated_at: datetime


class SystemConfigUpdate(BaseModel):
    config_value: object
    description: str | None = None


class ValidationCheck(BaseModel):
    name: str
    status: str
    detail: str
    count: int = 0


class ValidationReport(BaseModel):
    checked_at: datetime
    status: str
    checks: list[ValidationCheck]
    failures: int
