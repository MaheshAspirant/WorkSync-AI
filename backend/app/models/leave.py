"""Leave request and immutable leave-approval history models."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow
from app.models.enums import LeaveStatus, LeaveType
from app.models.master import enum_col

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.master import Employee, LeavePolicy


class LeaveRequest(Base, TimestampMixin):
    __tablename__ = "leave_requests"

    leave_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"), nullable=False, index=True
    )
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("leave_policies.policy_id"), nullable=False
    )
    leave_type: Mapped[LeaveType] = mapped_column(
        enum_col(LeaveType, 30), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_days: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeaveStatus] = mapped_column(
        enum_col(LeaveStatus, 30), default=LeaveStatus.PENDING, nullable=False, index=True
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    manager_comment: Mapped[str | None] = mapped_column(Text)

    employee: Mapped["Employee"] = relationship(back_populates="leave_requests")
    policy: Mapped["LeavePolicy"] = relationship(back_populates="leave_requests")
    decided_by: Mapped["User | None"] = relationship(foreign_keys=[decided_by_user_id])
    approvals: Mapped[list["LeaveApprovalHistory"]] = relationship(
        back_populates="leave_request", order_by="LeaveApprovalHistory.created_at"
    )

    @property
    def employee_name(self) -> str | None:
        return self.employee.full_name if self.employee else None

    @property
    def team_id(self) -> str | None:
        return self.employee.team_id if self.employee else None

    @property
    def history(self) -> list["LeaveApprovalHistory"]:
        return self.approvals


class LeaveApprovalHistory(Base):
    __tablename__ = "leave_approval_history"

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    leave_id: Mapped[str] = mapped_column(
        ForeignKey("leave_requests.leave_id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[LeaveStatus | None] = mapped_column(enum_col(LeaveStatus, 30))
    to_status: Mapped[LeaveStatus] = mapped_column(enum_col(LeaveStatus, 30), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    leave_request: Mapped["LeaveRequest"] = relationship(back_populates="approvals")
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_user_id])
