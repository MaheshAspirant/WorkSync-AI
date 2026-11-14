"""Aggregate API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    admin,
    analytics,
    attendance,
    audit,
    auth,
    employees,
    exceptions,
    health,
    leave,
    scheduling,
    swaps,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(leave.router)
api_router.include_router(scheduling.router)
api_router.include_router(swaps.router)
api_router.include_router(attendance.router)
api_router.include_router(exceptions.router)
api_router.include_router(analytics.router)
api_router.include_router(audit.router)
api_router.include_router(admin.router)
