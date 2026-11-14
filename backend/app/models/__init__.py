"""Import every ORM model so SQLAlchemy metadata is complete."""

from app.models.attendance import AttendanceEvent, EmployeeAvailability
from app.models.audit import AuditLog, IdCounter, SystemConfig
from app.models.auth import Role, User
from app.models.enums import *  # noqa: F401,F403
from app.models.leave import LeaveApprovalHistory, LeaveRequest
from app.models.master import (
    Employee,
    EmployeeSkill,
    HolidayCalendar,
    LeavePolicy,
    Shift,
    ShiftTemplate,
    Skill,
    Team,
    TeamManager,
)
from app.models.scheduling import (
    CoverageRequirement,
    SchedulingDecision,
    SchedulingException,
    SchedulingRun,
    ShiftAssignment,
    SwapApprovalHistory,
    SwapRequest,
)

__all__ = [
    "AttendanceEvent",
    "AuditLog",
    "CoverageRequirement",
    "Employee",
    "EmployeeAvailability",
    "EmployeeSkill",
    "HolidayCalendar",
    "IdCounter",
    "LeaveApprovalHistory",
    "LeavePolicy",
    "LeaveRequest",
    "Role",
    "SchedulingDecision",
    "SchedulingException",
    "SchedulingRun",
    "Shift",
    "ShiftAssignment",
    "ShiftTemplate",
    "Skill",
    "SwapApprovalHistory",
    "SwapRequest",
    "SystemConfig",
    "Team",
    "TeamManager",
    "User",
]
