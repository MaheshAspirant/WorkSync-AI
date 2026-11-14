"""Generator configuration and presets.

The same code path produces starter and full datasets; only the parameters
change.  The seed is fixed by default (20261022) so runs are reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = 20261022
DATASET_START = date(2026, 10, 1)
AS_OF_DATE = date(2026, 11, 14)


@dataclass(frozen=True)
class GenerationConfig:
    scale: str = "full"
    seed: int = DEFAULT_SEED
    teams: int = 100
    employees: int = 2000
    days: int = 90
    leave_requests: int = 5000
    swap_requests: int = 1000
    skills: int = 20
    shifts_per_day: int = 3
    start_date: date = DATASET_START
    as_of_date: date = AS_OF_DATE
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "database" / "seed" / "full")
    write_db: bool = True
    database_url: str | None = None

    @property
    def end_date(self) -> date:
        from datetime import timedelta

        return self.start_date + timedelta(days=self.days - 1)


def preset(scale: str, *, write_db: bool = True, output_dir: Path | None = None,
           database_url: str | None = None) -> GenerationConfig:
    if scale == "full":
        return GenerationConfig(
            scale="full",
            teams=100,
            employees=2000,
            days=90,
            leave_requests=5000,
            swap_requests=1000,
            output_dir=output_dir or (PROJECT_ROOT / "database" / "seed" / "full"),
            write_db=write_db,
            database_url=database_url,
        )
    if scale == "starter":
        return GenerationConfig(
            scale="starter",
            teams=20,
            employees=400,
            days=60,
            leave_requests=800,
            swap_requests=150,
            output_dir=output_dir or (PROJECT_ROOT / "database" / "seed" / "starter"),
            write_db=write_db,
            database_url=database_url,
        )
    raise ValueError(f"Unknown scale '{scale}' (expected full or starter)")
