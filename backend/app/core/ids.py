"""Deterministic, zero-padded, immutable business identifiers.

The ``id_counters`` row is locked (``SELECT ... FOR UPDATE`` on PostgreSQL) so
concurrent requests cannot produce duplicate identifiers.  SQLite serialises
writers, so the same code is safe there.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit import IdCounter


def next_id(
    db: Session,
    counter_key: str,
    prefix: str,
    width: int,
    *,
    year: int | None = None,
) -> str:
    counter = db.get(IdCounter, counter_key, with_for_update=True)
    if counter is None:
        counter = IdCounter(counter_key=counter_key, next_value=1)
        db.add(counter)
        db.flush()
    value = counter.next_value
    counter.next_value = value + 1
    db.flush()
    suffix = str(value).zfill(width)
    if year is not None:
        return f"{prefix}-{year}-{suffix}"
    return f"{prefix}-{suffix}"


def ensure_counter(db: Session, counter_key: str, next_value: int) -> None:
    """Idempotently raise a counter after bulk seeding."""
    counter = db.get(IdCounter, counter_key)
    if counter is None:
        db.add(IdCounter(counter_key=counter_key, next_value=next_value))
    elif counter.next_value < next_value:
        counter.next_value = next_value
