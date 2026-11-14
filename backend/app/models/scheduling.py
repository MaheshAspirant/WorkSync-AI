"""Scheduling, assignment, swap and exception models."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow
from app.models.enums import (
    AssignmentSource,
    AssignmentStatus,
    DayType,
    IssueType,
    ResolutionStatus,
    RunStatus,
    Severity,
    SolverStatus,
    SwapStatus,
)
from app.models.master import enum_col

if TYPE_CHECKING:
    from app.models.attendance import AttendanceEvent
    from app.models.auth import User
    from app.models.master import Employee, Shift, ShiftTemplate, Skill, Team


class CoverageRequirement(Base, TimestampMixin):
    """Minimum staffing for a team/shift/day-type, optionally per skill."""

    __tablename__ = "coverage_requirements"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "shift_template_id",
            "day_type",
            "effective_from",
            "skill_id",
            name="uq_coverage_version",
        ),
    )

    coverage_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.team_id"), nullable=False, index=True)
    shift_template_id: Mapped[str] = mapped_column(
        ForeignKey("shift_templates.shift_template_id"), nullable=False, index=True
    )
    skill_id: Mapped[str | None] = mapped_column(
        ForeignKey("skills.skill_id"), nullable=True, index=True
    )
    day_type: Mapped[DayType] = mapped_column(
        enum_col(DayType, 20), default=DayType.ALL, nullable=False
    )
    min_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)

    team: Mapped["Team"] = relationship(back_populates="coverage_requirements")
    shift_template: Mapped["ShiftTemplate"] = relationship(back_populates="coverage_requirements")
    skill: Mapped["Skill | None"] = relationship(back_populates="coverage_requirements")


class ShiftAssignment(Base, TimestampMixin):
    __tablename__ = "shift_assignments"
    # No unique (shift, employee) constraint: cancelled/swapped-out rows are
    # preserved as history and an employee may later be re-assigned to the same
    # shift.  Active duplicates are rejected by the assignment service and
    # checked by the validation suite.

    assignment_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    shift_id: Mapped[str] = mapped_column(ForeignKey("shifts.shift_id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"), nullable=False, index=True
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        enum_col(AssignmentStatus, 30), default=AssignmentStatus.SCHEDULED, nullable=False, index=True
    )
    assignment_source: Mapped[AssignmentSource] = mapped_column(
        enum_col(AssignmentSource, 20), default=AssignmentSource.MANUAL, nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    scheduled_hours: Mapped[float] = mapped_column(Float, nullable=False)
    is_overtime: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("scheduling_runs.run_id"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    shift: Mapped["Shift"] = relationship(back_populates="assignments")
    employee: Mapped["Employee"] = relationship(back_populates="assignments")
    run: Mapped["SchedulingRun | None"] = relationship(back_populates="assignments")
    decisions: Mapped[list["SchedulingDecision"]] = relationship(back_populates="assignment")
    attendance: Mapped["AttendanceEvent | None"] = relationship(back_populates="assignment")

    @property
    def employee_name(self) -> str | None:
        return self.employee.full_name if self.employee else None

    @property
    def shift_date(self):
        return self.shift.shift_date if self.shift else None

    @property
    def template_code(self) -> str | None:
        return self.shift.template.code if self.shift and self.shift.template else None

    @property
    def template_name(self) -> str | None:
        return self.shift.template.name if self.shift and self.shift.template else None

    @property
    def start_at(self):
        return self.shift.start_at if self.shift else None

    @property
    def end_at(self):
        return self.shift.end_at if self.shift else None


class SchedulingRun(Base, TimestampMixin):
    __tablename__ = "scheduling_runs"

    run_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.team_id"), index=True)
    scope_start: Mapped[date] = mapped_column(Date, nullable=False)
    scope_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        enum_col(RunStatus, 20), default=RunStatus.RUNNING, nullable=False, index=True
    )
    solver_status: Mapped[SolverStatus] = mapped_column(
        enum_col(SolverStatus, 20), default=SolverStatus.NOT_RUN, nullable=False
    )
    objective_value: Mapped[float | None] = mapped_column(Float)
    assignments_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coverage_gaps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hard_violations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    soft_score: Mapped[float | None] = mapped_column(Float)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    team: Mapped["Team | None"] = relationship()
    assignments: Mapped[list["ShiftAssignment"]] = relationship(back_populates="run")
    decisions: Mapped[list["SchedulingDecision"]] = relationship(back_populates="run")
    exceptions: Mapped[list["SchedulingException"]] = relationship(back_populates="run")

    @property
    def team_name(self) -> str | None:
        return self.team.name if self.team else None

    @property
    def message(self) -> str | None:
        return (self.parameters or {}).get("message")


class SchedulingDecision(Base):
    __tablename__ = "scheduling_decisions"

    decision_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("scheduling_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    shift_id: Mapped[str] = mapped_column(ForeignKey("shifts.shift_id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"), nullable=False, index=True
    )
    assignment_id: Mapped[str | None] = mapped_column(
        ForeignKey("shift_assignments.assignment_id"), unique=True, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    skill_match: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    availability_result: Mapped[str] = mapped_column(String(40), nullable=False)
    leave_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    constraint_evaluation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    optimization_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    run: Mapped["SchedulingRun"] = relationship(back_populates="decisions")
    assignment: Mapped["ShiftAssignment | None"] = relationship(back_populates="decisions")
    shift: Mapped["Shift"] = relationship()
    employee: Mapped["Employee"] = relationship()

    @property
    def employee_name(self) -> str | None:
        return self.employee.full_name if self.employee else None

    @property
    def shift_date(self):
        return self.shift.shift_date if self.shift else None

    @property
    def template_code(self) -> str | None:
        return self.shift.template.code if self.shift and self.shift.template else None


class SchedulingException(Base, TimestampMixin):
    __tablename__ = "scheduling_exceptions"

    issue_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("scheduling_runs.run_id"), nullable=True, index=True
    )
    issue_type: Mapped[IssueType] = mapped_column(
        enum_col(IssueType, 40), nullable=False, index=True
    )
    employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.employee_id"), nullable=True, index=True
    )
    shift_id: Mapped[str | None] = mapped_column(
        ForeignKey("shifts.shift_id"), nullable=True, index=True
    )
    assignment_id: Mapped[str | None] = mapped_column(
        ForeignKey("shift_assignments.assignment_id"), nullable=True
    )
    transaction_type: Mapped[str | None] = mapped_column(String(30))
    transaction_id: Mapped[str | None] = mapped_column(String(30), index=True)
    severity: Mapped[Severity] = mapped_column(
        enum_col(Severity, 20), default=Severity.MEDIUM, nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detection_source: Mapped[str] = mapped_column(String(40), default="RUNTIME", nullable=False)
    resolution_status: Mapped[ResolutionStatus] = mapped_column(
        enum_col(ResolutionStatus, 20), default=ResolutionStatus.OPEN, nullable=False, index=True
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    resolved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)

    run: Mapped["SchedulingRun | None"] = relationship(back_populates="exceptions")
    employee: Mapped["Employee | None"] = relationship()
    shift: Mapped["Shift | None"] = relationship()
    assignment: Mapped["ShiftAssignment | None"] = relationship()
    resolved_by: Mapped["User | None"] = relationship(foreign_keys=[resolved_by_user_id])

    @property
    def employee_name(self) -> str | None:
        return self.employee.full_name if self.employee else None

    @property
    def shift_date(self):
        return self.shift.shift_date if self.shift else None


class SwapRequest(Base, TimestampMixin):
    __tablename__ = "swap_requests"

    swap_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    requester_employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"), nullable=False, index=True
    )
    target_employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"), nullable=False, index=True
    )
    requester_assignment_id: Mapped[str] = mapped_column(
        ForeignKey("shift_assignments.assignment_id"), nullable=False
    )
    target_assignment_id: Mapped[str] = mapped_column(
        ForeignKey("shift_assignments.assignment_id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SwapStatus] = mapped_column(
        enum_col(SwapStatus, 20), default=SwapStatus.REQUESTED, nullable=False, index=True
    )
    requester_agreed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    target_agreed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    target_responded_at: Mapped[datetime | None] = mapped_column(DateTime)
    manager_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decision_comment: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)

    requester: Mapped["Employee"] = relationship(foreign_keys=[requester_employee_id])
    target: Mapped["Employee"] = relationship(foreign_keys=[target_employee_id])
    requester_assignment: Mapped["ShiftAssignment"] = relationship(
        foreign_keys=[requester_assignment_id]
    )
    target_assignment: Mapped["ShiftAssignment"] = relationship(
        foreign_keys=[target_assignment_id]
    )
    manager: Mapped["User | None"] = relationship(foreign_keys=[manager_user_id])
    approvals: Mapped[list["SwapApprovalHistory"]] = relationship(
        back_populates="swap", order_by="SwapApprovalHistory.created_at"
    )

    @property
    def history(self) -> list["SwapApprovalHistory"]:
        return self.approvals

    @property
    def requester_name(self) -> str | None:
        return self.requester.full_name if self.requester else None

    @property
    def target_name(self) -> str | None:
        return self.target.full_name if self.target else None

    @staticmethod
    def _shift_of(assignment: "ShiftAssignment | None"):
        return assignment.shift if assignment else None

    @property
    def requester_shift_date(self):
        shift = self._shift_of(self.requester_assignment)
        return shift.shift_date if shift else None

    @property
    def target_shift_date(self):
        shift = self._shift_of(self.target_assignment)
        return shift.shift_date if shift else None

    @property
    def requester_shift_code(self) -> str | None:
        shift = self._shift_of(self.requester_assignment)
        return shift.template.code if shift and shift.template else None

    @property
    def target_shift_code(self) -> str | None:
        shift = self._shift_of(self.target_assignment)
        return shift.template.code if shift and shift.template else None


class SwapApprovalHistory(Base):
    __tablename__ = "swap_approval_history"

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    swap_id: Mapped[str] = mapped_column(
        ForeignKey("swap_requests.swap_id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[SwapStatus | None] = mapped_column(enum_col(SwapStatus, 20))
    to_status: Mapped[SwapStatus] = mapped_column(enum_col(SwapStatus, 20), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    swap: Mapped["SwapRequest"] = relationship(back_populates="approvals")
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_user_id])
