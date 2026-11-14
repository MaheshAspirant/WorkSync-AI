"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import db_session

router = APIRouter(tags=["Health"])


@router.get("/health")
def health(db: Session = Depends(db_session)):
    database_ok = False
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        database_ok = False
    return {
        "status": "ok" if database_ok else "degraded",
        "service": "WorkSync AI API",
        "database": "ok" if database_ok else "unavailable",
    }
