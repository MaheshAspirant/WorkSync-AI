"""Employee, team, skill, availability and reference-data schemas."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import EmployeeStatus, EmploymentType, ShiftPreference, ShiftStatus

COMMON_CONFIG = ConfigDict(from_attributes=True)


class EmployeeSkillOut(BaseModel):
    model_config = COMMON_CONFIG

    skill_id: str
    skill_name: str | None = None
    category: str | None = None
    proficiency: int
    certified: bool
    years_experience: float


class EmployeeSkillIn(BaseModel):
    skill_id: str
    proficiency: int = Field(default=3, ge=1, le=5)
    certified: bool = False
    years_experience: float = Field(default=0, ge=0, le=50)


class EmployeeOut(BaseModel):
    model_config = COMMON_CONFIG

    employee_id: str
    team_id: str
    team_name: str | None = None
    first_name: str
    last_name: str
    full_name: str | None = None
    email: EmailStr
    phone: str | None = None
    job_title: str
    employment_type: EmploymentType
    hire_date: date
    status: EmployeeStatus
    weekly_hours_cap: float
    daily_hours_cap: float
    overtime_cap_weekly: float
    min_rest_hours: float
    preferred_shift: ShiftPreference
    created_at: datetime | None = None
    skills: list[EmployeeSkillOut] = []


class EmployeeCreate(BaseModel):
    team_id: str
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    job_title: str = Field(min_length=2, max_length=80)
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    hire_date: date
    weekly_hours_cap: float = Field(default=40, gt=0, le=60)
    daily_hours_cap: float = Field(default=8, gt=0, le=16)
    overtime_cap_weekly: float = Field(default=10, ge=0, le=30)
    min_rest_hours: float = Field(default=11, ge=0, le=24)
    preferred_shift: ShiftPreference = ShiftPreference.NONE
    skills: list[EmployeeSkillIn] = []


class EmployeeUpdate(BaseModel):
    team_id: str | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=60)
    last_name: str | None = Field(default=None, min_length=1, max_length=60)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    job_title: str | None = Field(default=None, min_length=2, max_length=80)
    employment_type: EmploymentType | None = None
    status: EmployeeStatus | None = None
    weekly_hours_cap: float | None = Field(default=None, gt=0, le=60)
    daily_hours_cap: float | None = Field(default=None, gt=0, le=16)
    overtime_cap_weekly: float | None = Field(default=None, ge=0, le=30)
    min_rest_hours: float | None = Field(default=None, ge=0, le=24)
    preferred_shift: ShiftPreference | None = None


class AvailabilityOut(BaseModel):
    model_config = COMMON_CONFIG

    availability_id: int
    employee_id: str
    day_of_week: int
    is_available: bool
    available_from: time
    available_to: time
    effective_from: date
    effective_to: date | None = None


class AvailabilityCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    is_available: bool = True
    available_from: time = time(0, 0)
    available_to: time = time(23, 59)
    effective_from: date
    effective_to: date | None = None


class TeamOut(BaseModel):
    model_config = COMMON_CONFIG

    team_id: str
    name: str
    department: str
    site: str
    cost_center: str | None = None
    timezone: str
    is_active: bool
    headcount: int = 0
    manager_name: str | None = None


class TeamCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    department: str = Field(min_length=2, max_length=60)
    site: str = Field(min_length=2, max_length=80)
    cost_center: str | None = Field(default=None, max_length=30)
    timezone: str = "Asia/Kolkata"
    manager_employee_id: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    department: str | None = None
    site: str | None = None
    cost_center: str | None = None
    is_active: bool | None = None
    manager_employee_id: str | None = None


class SkillOut(BaseModel):
    model_config = COMMON_CONFIG

    skill_id: str
    name: str
    category: str
    description: str | None = None
    is_critical: bool
    employee_count: int = 0


class SkillCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: str = Field(min_length=2, max_length=50)
    description: str | None = None
    is_critical: bool = False


class ShiftTemplateOut(BaseModel):
    model_config = COMMON_CONFIG

    shift_template_id: str
    code: str
    name: str
    start_time: time
    end_time: time
    duration_hours: float
    crosses_midnight: bool
    color: str


class HolidayOut(BaseModel):
    model_config = COMMON_CONFIG

    holiday_id: str
    holiday_date: date
    name: str
    region: str
    is_paid: bool
    is_recurring: bool


class ShiftOut(BaseModel):
    model_config = COMMON_CONFIG

    shift_id: str
    shift_date: date
    shift_template_id: str
    template_code: str | None = None
    template_name: str | None = None
    team_id: str
    team_name: str | None = None
    start_at: datetime
    end_at: datetime
    required_staff: int
    status: ShiftStatus
    assigned_count: int = 0
    coverage_status: str = "OK"


class AssignmentOut(BaseModel):
    model_config = COMMON_CONFIG

    assignment_id: str
    shift_id: str
    employee_id: str
    employee_name: str | None = None
    shift_date: date | None = None
    template_code: str | None = None
    template_name: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: str
    assignment_source: str
    scheduled_hours: float
    is_overtime: bool
    run_id: str | None = None
    assigned_at: datetime | None = None
    notes: str | None = None
