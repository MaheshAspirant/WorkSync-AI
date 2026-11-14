"""Attendance events and employee availability (effective-dated)."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow
from app.models.enums import (
    AttendanceSource,
    AttendanceStatus,
    ReconciliationStatus,
)
from app.models.master import enum_col

if TYPE_CHECKING:
    from app.models.master import Employee, Shift
    from app.models.scheduling import ShiftAssignment


class EmployeeAvailability(Base, TimestampMixin):
    """Recurring weekly availability, effective-dated.

    ``day_of_week`` follows Python's convention: Monday = 0 ... Sunday = 6.
    A missing row means "no restriction" and is treated as available.
    """

    __tablename__ = "employee_availability"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "day_of_week", "effective_from", name="uq_availability_version"
        ),
    )

    availability_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    available_from: Mapped[time] = mapped_column(Time, default=time(0, 0), nullable=False)
    available_to: Mapped[time] = mapped_column(Time, default=time(23, 59), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)

    employee: Mapped["Employee"] = relationship(back_populates="availabilities")


class AttendanceEvent(Base, TimestampMixin):
    __tablename__ = "attendance_events"

    attendance_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"), nullable=False, index=True
    )
    shift_id: Mapped[str | None] = mapped_column(ForeignKey("shifts.shift_id"), index=True)
    assignment_id: Mapped[str | None] = mapped_column(
        ForeignKey("shift_assignments.assignment_id"), unique=True, index=True
    )
    scheduled_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_check_in: Mapped[datetime | None] = mapped_column(DateTime)
    actual_check_out: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[AttendanceStatus] = mapped_column(
        enum_col(AttendanceStatus, 30), nullable=False, index=True
    )
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    early_departure_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actual_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    overtime_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source: Mapped[AttendanceSource] = mapped_column(
        enum_col(AttendanceSource, 20), default=AttendanceSource.BIOMETRIC, nullable=False
    )
    reconciliation_status: Mapped[ReconciliationStatus] = mapped_column(
        enum_col(ReconciliationStatus, 20),
        default=ReconciliationStatus.MATCHED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    employee: Mapped["Employee"] = relationship(back_populates="attendance_events")
    shift: Mapped["Shift | None"] = relationship(back_populates="attendance_events")
    assignment: Mapped["ShiftAssignment | None"] = relationship(back_populates="attendance")

    @property
    def employee_name(self) -> str | None:
        return self.employee.full_name if self.employee else None

    @property
    def shift_date(self):
        return self.shift.shift_date if self.shift else None
