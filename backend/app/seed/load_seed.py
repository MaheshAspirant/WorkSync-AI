"""Load generated CSV seed data into the configured database.

Examples
--------
    python -m app.seed.load_seed --scale full
    python -m app.seed.load_seed --scale starter --data-dir ../database/seed/starter
    python -m app.seed.load_seed --force

The loader is idempotent by default: if employees already exist it does nothing
except ensure bootstrap roles/users/configuration.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime, time
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT, settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Employee  # noqa: F401
from app.models import *  # noqa: F401,F403
from app.seed.bootstrap import bootstrap

TABLE_ORDER = [
    "teams",
    "skills",
    "employees",
    "employee_skills",
    "employee_availability",
    "team_managers",
    "shift_templates",
    "coverage_requirements",
    "holiday_calendar",
    "leave_policies",
    "leave_requests",
    "leave_approval_history",
    "shifts",
    "shift_assignments",
    "attendance_events",
    "swap_requests",
    "swap_approval_history",
]


def _parse_value(value: str, column):
    if value == "":
        return None
    try:
        python_type = column.type.python_type
    except (NotImplementedError, AttributeError):
        return value
    if python_type is bool:
        return value.strip().lower() in {"1", "true", "yes", "t"}
    if python_type is int:
        return int(float(value))
    if python_type is float:
        return float(value)
    if python_type is datetime:
        return datetime.fromisoformat(value)
    if python_type is date:
        return date.fromisoformat(value[:10])
    if python_type is time:
        return time.fromisoformat(value)
    return value


def _clear_data(db: Session) -> None:
    tables = [
        "audit_logs", "scheduling_exceptions", "scheduling_decisions", "scheduling_runs",
        "swap_approval_history", "swap_requests", "attendance_events", "shift_assignments",
        "leave_approval_history", "leave_requests", "shifts", "coverage_requirements",
        "team_managers", "employee_availability", "employee_skills", "users", "employees",
        "teams", "skills", "shift_templates", "holiday_calendar", "leave_policies",
        "id_counters",
    ]
    for table_name in tables:
        if table_name in Base.metadata.tables:
            db.execute(Base.metadata.tables[table_name].delete())
    db.commit()


def load(data_dir: Path, force: bool = False) -> int:
    if not data_dir.exists():
        print(f"Seed directory not found: {data_dir}", file=sys.stderr)
        return 2
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        existing = db.execute(select(Employee)).first()
        if existing and not force:
            print("Database already contains employees; bootstrap only (use --force to reload).")
            bootstrap(db)
            return 0
        if force:
            print("Clearing operational tables (roles are retained)…")
            _clear_data(db)

        for table_name in TABLE_ORDER:
            csv_path = data_dir / "csv" / f"{table_name}.csv"
            if not csv_path.exists():
                continue
            table = Base.metadata.tables[table_name]
            columns = list(table.columns)
            with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                batch = []
                total = 0
                for row in reader:
                    record = {}
                    for column in columns:
                        if column.name in row:
                            record[column.name] = _parse_value(row[column.name], column)
                    batch.append(record)
                    if len(batch) >= 2000:
                        db.execute(table.insert(), batch)
                        total += len(batch)
                        batch = []
                if batch:
                    db.execute(table.insert(), batch)
                    total += len(batch)
            print(f"  loaded {table_name}: {total:,}")
            db.commit()
        info = bootstrap(db)
        print(f"Bootstrap complete: {info}")
        # Verify loaded row counts.
        for table_name in ("employees", "teams", "shifts", "leave_requests", "shift_assignments"):
            count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
            print(f"  {table_name}: {count:,}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", choices=["full", "starter"], default="full")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    data_dir = args.data_dir or (PROJECT_ROOT / "database" / "seed" / args.scale)
    print(f"Loading seed from {data_dir}")
    print(f"Database: {settings.database_url}")
    return load(data_dir, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
