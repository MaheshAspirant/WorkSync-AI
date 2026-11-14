"""Attendance and overtime schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AttendanceSource, AttendanceStatus, ReconciliationStatus


class AttendanceCreate(BaseModel):
    assignment_id: str
    check_in: datetime | None = None
    check_out: datetime | None = None
    status: AttendanceStatus | None = None
    source: AttendanceSource = AttendanceSource.MANUAL
    notes: str | None = Field(default=None, max_length=500)


class AttendanceUpdate(BaseModel):
    check_in: datetime | None = None
    check_out: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attendance_id: str
    employee_id: str
    employee_name: str | None = None
    shift_id: str | None = None
    assignment_id: str | None = None
    shift_date: date | None = None
    scheduled_start: datetime
    scheduled_end: datetime
    actual_check_in: datetime | None = None
    actual_check_out: datetime | None = None
    status: AttendanceStatus
    late_minutes: int
    early_departure_minutes: int
    actual_hours: float
    overtime_hours: float
    source: AttendanceSource
    reconciliation_status: ReconciliationStatus
    notes: str | None = None


class AttendanceSummary(BaseModel):
    employee_id: str | None = None
    period_start: date
    period_end: date
    scheduled_shifts: int
    attended_shifts: int
    absent_shifts: int
    late_events: int
    total_scheduled_hours: float
    total_actual_hours: float
    total_overtime_hours: float
    absence_rate: float


class OvertimeEmployeeRow(BaseModel):
    employee_id: str
    employee_name: str
    team_id: str
    week_start: date
    scheduled_hours: float
    actual_hours: float
    overtime_hours: float
    overtime_cap: float
    cap_exceeded: bool


class OvertimeSummary(BaseModel):
    period_start: date
    period_end: date
    total_overtime_hours: float
    average_overtime_per_employee: float
    employees_over_cap: int
    rows: list[OvertimeEmployeeRow]
