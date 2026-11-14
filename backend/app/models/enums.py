"""Domain enumerations shared by ORM models, schemas and services."""

from __future__ import annotations

from enum import Enum


class EmployeeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ON_LEAVE = "ON_LEAVE"
    TERMINATED = "TERMINATED"


class EmploymentType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERN = "INTERN"


class ShiftPreference(str, Enum):
    MORNING = "MORNING"
    EVENING = "EVENING"
    NIGHT = "NIGHT"
    NONE = "NONE"


class ShiftStatus(str, Enum):
    PLANNED = "PLANNED"
    PUBLISHED = "PUBLISHED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AssignmentStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    SWAPPED_OUT = "SWAPPED_OUT"
    SWAPPED_IN = "SWAPPED_IN"
    NO_SHOW = "NO_SHOW"


class AssignmentSource(str, Enum):
    BASELINE = "BASELINE"
    OPTIMIZER = "OPTIMIZER"
    MANUAL = "MANUAL"
    SWAP = "SWAP"


class LeaveType(str, Enum):
    ANNUAL = "ANNUAL"
    SICK = "SICK"
    UNPAID = "UNPAID"
    PARENTAL = "PARENTAL"
    BEREAVEMENT = "BEREAVEMENT"


class LeaveStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class AttendanceStatus(str, Enum):
    PRESENT = "PRESENT"
    LATE = "LATE"
    ABSENT = "ABSENT"
    EARLY_DEPARTURE = "EARLY_DEPARTURE"
    NO_SHOW = "NO_SHOW"
    ON_LEAVE = "ON_LEAVE"


class AttendanceSource(str, Enum):
    BIOMETRIC = "BIOMETRIC"
    MANUAL = "MANUAL"
    MOBILE = "MOBILE"


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"
    PENDING = "PENDING"


class DayType(str, Enum):
    ALL = "ALL"
    WEEKDAY = "WEEKDAY"
    WEEKEND = "WEEKEND"
    HOLIDAY = "HOLIDAY"


class SwapStatus(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    APPLIED = "APPLIED"


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    INFEASIBLE = "INFEASIBLE"
    FAILED = "FAILED"


class SolverStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    NOT_RUN = "NOT_RUN"


class IssueType(str, Enum):
    DOUBLE_BOOKING = "DOUBLE_BOOKING"
    LEAVE_OVERLAP = "LEAVE_OVERLAP"
    MISSING_SKILL = "MISSING_SKILL"
    OVERTIME_CAP = "OVERTIME_CAP"
    UNAPPROVED_SWAP = "UNAPPROVED_SWAP"
    COVERAGE_GAP = "COVERAGE_GAP"
    REST_VIOLATION = "REST_VIOLATION"
    HOURS_CAP = "HOURS_CAP"
    ATTENDANCE_MISMATCH = "ATTENDANCE_MISMATCH"
    INVALID_ASSIGNMENT = "INVALID_ASSIGNMENT"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResolutionStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class RoleName(str, Enum):
    ADMIN = "ADMIN"
    HR = "HR"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class ShiftCode(str, Enum):
    MORNING = "A"
    EVENING = "B"
    NIGHT = "C"

    @property
    def preference(self) -> ShiftPreference:
        return {
            ShiftCode.MORNING: ShiftPreference.MORNING,
            ShiftCode.EVENING: ShiftPreference.EVENING,
            ShiftCode.NIGHT: ShiftPreference.NIGHT,
        }[self]
