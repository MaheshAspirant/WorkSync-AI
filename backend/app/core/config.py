"""Application configuration.

All runtime configuration is environment-driven (12-factor style).  A SQLite
database is used by default so the project can be executed on a developer
machine without PostgreSQL; Docker Compose supplies a PostgreSQL URL.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_CONFIG_PATH = Path(__file__).resolve()
PROJECT_ROOT = _CONFIG_PATH.parents[3]
# In the Docker image the backend is copied to /app (so app/core/config.py is
# only three levels below the project root).
if not (PROJECT_ROOT / "backend").exists():
    PROJECT_ROOT = _CONFIG_PATH.parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -----------------------------------------------------
    app_name: str = "WorkSync AI"
    environment: str = "development"
    api_prefix: str = "/api"
    debug: bool = False

    # --- Database --------------------------------------------------------
    # Example PostgreSQL: postgresql+psycopg://worksync:worksync@db:5432/worksync
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'backend' / 'worksync.db').as_posix()}"
    db_echo: bool = False

    # --- Security --------------------------------------------------------
    jwt_secret: str = "worksync-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    # --- Workforce policy defaults ---------------------------------------
    standard_weekly_hours: float = 40.0
    standard_daily_hours: float = 8.0
    default_overtime_cap_weekly: float = 10.0
    default_min_rest_hours: float = 11.0
    default_min_staff: int = 2

    # --- Scheduling ------------------------------------------------------
    scheduler_time_limit_seconds: float = 12.0
    scheduler_max_horizon_days: int = 31
    scheduler_default_horizon_days: int = 7

    # --- Data ------------------------------------------------------------
    seed: int = 20261022
    seed_data_dir: Path = PROJECT_ROOT / "database" / "seed"
    ground_truth_dir: Path = PROJECT_ROOT / "ground_truth"
    # First-run convenience: if the database is empty and the full CSV seed is
    # present, load it automatically before bootstrapping demo users.
    auto_seed_demo_data: bool = True

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
