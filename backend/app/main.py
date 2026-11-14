"""WorkSync AI FastAPI application (Application Tier entry point)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import BusinessRuleError
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.seed.bootstrap import bootstrap

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("worksync")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_dir = settings.seed_data_dir / "full"
    if settings.auto_seed_demo_data and (seed_dir / "csv" / "employees.csv").exists():
        from sqlalchemy import func, select

        from app.models import Employee

        with SessionLocal() as db:
            employee_count = db.execute(select(func.count()).select_from(Employee)).scalar_one()
        if employee_count == 0:
            logger.info("Empty database detected; loading seed data from %s", seed_dir)
            from app.seed.load_seed import load

            load(seed_dir)
    with SessionLocal() as db:
        info = bootstrap(db)
        logger.info("Bootstrap complete: %s", info)
    logger.info("WorkSync AI API ready (env=%s, db=%s)", settings.environment,
                "sqlite" if settings.is_sqlite else "postgresql")
    yield


app = FastAPI(
    title="WorkSync AI – Intelligent Workforce Scheduling & Leave Management",
    description=(
        "Three-tier workforce management API. Generates fair, feasible schedules "
        "with OR-Tools CP-SAT, manages leave and swaps, records attendance, computes "
        "overtime and detects labelled exceptions with full auditability."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BusinessRuleError)
async def business_error_handler(_request: Request, exc: BusinessRuleError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": exc.message, "details": exc.details},
            "detail": exc.message,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    details = jsonable_encoder(exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": details},
            },
            "detail": "Request validation failed",
        },
    )


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": {}},
            "detail": message,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled application error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. The incident has been logged.",
                "details": {},
            },
            "detail": "An unexpected error occurred.",
        },
    )


app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "WorkSync AI",
        "version": "1.0.0",
        "tier": "application",
        "docs": "/docs",
        "api": settings.api_prefix,
    }
