"""Master / reference data models."""

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
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow
from app.models.enums import (
    DayType,
    EmployeeStatus,
    EmploymentType,
    ShiftPreference,
    ShiftStatus,
)

if TYPE_CHECKING:
    from app.models.attendance import AttendanceEvent, EmployeeAvailability
    from app.models.leave import LeaveRequest
    from app.models.scheduling import (
        CoverageRequirement,
        ShiftAssignment,
        SwapRequest,
    )


def enum_col(enum_cls, length: int = 40, **kwargs):
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        validate_strings=True,
        values_callable=lambda e: [x.value for x in e],
        **kwargs,
    )


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    team_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    department: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    site: Mapped[str] = mapped_column(String(80), nullable=False)
    cost_center: Mapped[str | None] = mapped_column(String(30))
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Kolkata", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    employees: Mapped[list["Employee"]] = relationship(back_populates="team")
    managers: Mapped[list["TeamManager"]] = relationship(back_populates="team")
    shifts: Mapped[list["Shift"]] = relationship(back_populates="team")
    coverage_requirements: Mapped[list["CoverageRequirement"]] = relationship(
        back_populates="team"
    )


class TeamManager(Base, TimestampMixin):
    """Manager assignment history for a team (many managers over time)."""

    __tablename__ = "team_managers"
    __table_args__ = (
        UniqueConstraint("team_id", "employee_id", "effective_from", name="uq_team_manager_version"),
    )

    team_manager_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.team_id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"), nullable=False, index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)

    team: Mapped["Team"] = relationship(back_populates="managers")
    employee: Mapped["Employee"] = relationship(back_populates="manager_roles")


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"

    skill_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    employee_skills: Mapped[list["EmployeeSkill"]] = relationship(back_populates="skill")
    coverage_requirements: Mapped[list["CoverageRequirement"]] = relationship(
        back_populates="skill"
    )


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    employee_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    team_id: Mapped[str] = mapped_column(
        ForeignKey("teams.team_id"), nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(60), nullable=False)
    last_name: Mapped[str] = mapped_column(String(60), nullable=False)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    job_title: Mapped[str] = mapped_column(String(80), nullable=False)
    employment_type: Mapped[EmploymentType] = mapped_column(
        enum_col(EmploymentType), default=EmploymentType.FULL_TIME, nullable=False
    )
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[EmployeeStatus] = mapped_column(
        enum_col(EmployeeStatus), default=EmployeeStatus.ACTIVE, nullable=False, index=True
    )
    weekly_hours_cap: Mapped[float] = mapped_column(Float, default=40.0, nullable=False)
    daily_hours_cap: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    overtime_cap_weekly: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    min_rest_hours: Mapped[float] = mapped_column(Float, default=11.0, nullable=False)
    preferred_shift: Mapped[ShiftPreference] = mapped_column(
        enum_col(ShiftPreference, 20), default=ShiftPreference.NONE, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)

    team: Mapped["Team"] = relationship(back_populates="employees")
    skills: Mapped[list["EmployeeSkill"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    manager_roles: Mapped[list["TeamManager"]] = relationship(back_populates="employee")
    assignments: Mapped[list["ShiftAssignment"]] = relationship(back_populates="employee")
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(back_populates="employee")
    attendance_events: Mapped[list["AttendanceEvent"]] = relationship(back_populates="employee")
    availabilities: Mapped[list["EmployeeAvailability"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def team_name(self) -> str | None:
        return self.team.name if self.team else None


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"

    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(
        ForeignKey("skills.skill_id", ondelete="CASCADE"), primary_key=True, index=True
    )
    proficiency: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    certified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    years_experience: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    employee: Mapped["Employee"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(back_populates="employee_skills")

    @property
    def skill_name(self) -> str | None:
        return self.skill.name if self.skill else None

    @property
    def category(self) -> str | None:
        return self.skill.category if self.skill else None


class ShiftTemplate(Base, TimestampMixin):
    __tablename__ = "shift_templates"

    shift_template_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#2563eb", nullable=False)

    shifts: Mapped[list["Shift"]] = relationship(back_populates="template")
    coverage_requirements: Mapped[list["CoverageRequirement"]] = relationship(
        back_populates="shift_template"
    )


class Shift(Base, TimestampMixin):
    """A dated, team-specific instance of a shift template."""

    __tablename__ = "shifts"
    __table_args__ = (
        UniqueConstraint(
            "team_id", "shift_date", "shift_template_id", name="uq_shift_team_date_template"
        ),
    )

    shift_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_template_id: Mapped[str] = mapped_column(
        ForeignKey("shift_templates.shift_template_id"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.team_id"), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    required_staff: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    status: Mapped[ShiftStatus] = mapped_column(
        enum_col(ShiftStatus), default=ShiftStatus.PUBLISHED, nullable=False
    )

    team: Mapped["Team"] = relationship(back_populates="shifts")
    template: Mapped["ShiftTemplate"] = relationship(back_populates="shifts")
    assignments: Mapped[list["ShiftAssignment"]] = relationship(back_populates="shift")
    attendance_events: Mapped[list["AttendanceEvent"]] = relationship(back_populates="shift")

    @property
    def template_code(self) -> str | None:
        return self.template.code if self.template else None

    @property
    def template_name(self) -> str | None:
        return self.template.name if self.template else None

    @property
    def team_name(self) -> str | None:
        return self.team.name if self.team else None

    @property
    def assigned_count(self) -> int:
        inactive = {"CANCELLED", "SWAPPED_OUT"}
        return sum(1 for a in self.assignments if getattr(a.status, "value", a.status) not in inactive)

    @property
    def coverage_status(self) -> str:
        count = self.assigned_count
        if count >= self.required_staff:
            return "OK"
        if count == 0:
            return "UNFILLED"
        return "UNDERSTAFFED"


class HolidayCalendar(Base, TimestampMixin):
    __tablename__ = "holiday_calendar"
    __table_args__ = (
        UniqueConstraint("holiday_date", "region", name="uq_holiday_date_region"),
    )

    holiday_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(20), default="IN", nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class LeavePolicy(Base, TimestampMixin):
    __tablename__ = "leave_policies"

    policy_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    leave_type: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    annual_entitlement_days: Mapped[float] = mapped_column(Float, nullable=False)
    max_consecutive_days: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_document_after_days: Mapped[int | None] = mapped_column(Integer)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_notice_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    leave_requests: Mapped[list["LeaveRequest"]] = relationship(back_populates="policy")
