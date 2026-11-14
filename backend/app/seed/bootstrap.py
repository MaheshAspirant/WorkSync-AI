"""Idempotent bootstrap: roles, policies, demo users, counters.

This runs on every application start.  It never duplicates rows and never
overwrites business data.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.ids import ensure_counter
from app.core.security import hash_password
from app.models.attendance import AttendanceEvent
from app.models.auth import Role, User
from app.models.enums import RoleName
from app.models.leave import LeaveRequest
from app.models.master import Employee, LeavePolicy, Skill, Team, TeamManager
from app.models.scheduling import (
    SchedulingException,
    SchedulingRun,
    ShiftAssignment,
    SwapRequest,
)
from app.services.config_service import ensure_defaults

ROLES = [
    ("ROLE-001", RoleName.ADMIN, "System administrator with full access",
     ["*"]),
    ("ROLE-002", RoleName.HR, "HR partner: people, leave policy and reporting",
     ["employees:*", "leave:*", "attendance:read", "analytics:*", "audit:read"]),
    ("ROLE-003", RoleName.MANAGER, "Team manager: scheduling and approvals",
     ["team:read", "schedule:*", "leave:approve", "swap:approve", "analytics:read"]),
    ("ROLE-004", RoleName.EMPLOYEE, "Employee self-service",
     ["self:read", "leave:request", "swap:request", "attendance:self"]),
]

POLICIES = [
    ("POL-001", "ANNUAL", 20, 15, None, True, 7,
     "Paid annual leave; 20 days per calendar year."),
    ("POL-002", "SICK", 10, 5, 2, True, 0,
     "Paid sick leave; medical note required after 2 consecutive days."),
    ("POL-003", "UNPAID", 30, 30, None, False, 3,
     "Unpaid personal leave, subject to manager approval."),
    ("POL-004", "PARENTAL", 90, 90, 1, True, 30,
     "Parental leave with documentation."),
    ("POL-005", "BEREAVEMENT", 5, 5, None, True, 0,
     "Compassionate / bereavement leave."),
]

DEMO_USERS = [
    ("USR-000001", "admin", "admin@worksync.ai", "Admin@123", RoleName.ADMIN, None),
    ("USR-000002", "hr", "hr@worksync.ai", "Hr@12345", RoleName.HR, "HR_EMPLOYEE"),
    ("USR-000003", "manager", "manager@worksync.ai", "Manager@123", RoleName.MANAGER, "MANAGER_EMPLOYEE"),
    ("USR-000004", "employee", "employee@worksync.ai", "Employee@123", RoleName.EMPLOYEE, "EMP-000001"),
]


def _first_manager_employee(db: Session, exclude: set[str] | None = None) -> Employee | None:
    exclude = exclude or set()
    rows = db.execute(
        select(TeamManager)
        .where(
            TeamManager.effective_from <= date.today(),
            (TeamManager.effective_to.is_(None)) | (TeamManager.effective_to >= date.today()),
        )
        .order_by(TeamManager.team_id)
    ).scalars().all()
    for row in rows:
        if row.employee_id not in exclude:
            return db.get(Employee, row.employee_id)
    return None


def _seed_roles(db: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for role_id, name, description, permissions in ROLES:
        role = db.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
        if role is None:
            role = Role(
                role_id=role_id,
                name=name,
                description=description,
                permissions=permissions,
            )
            db.add(role)
        roles[name.value] = role
    db.flush()
    return roles


def _seed_policies(db: Session) -> None:
    for policy_id, leave_type, entitlement, consecutive, document_after, paid, notice, description in POLICIES:
        existing = db.execute(
            select(LeavePolicy).where(LeavePolicy.leave_type == leave_type)
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                LeavePolicy(
                    policy_id=policy_id,
                    leave_type=leave_type,
                    annual_entitlement_days=entitlement,
                    max_consecutive_days=consecutive,
                    requires_document_after_days=document_after,
                    is_paid=paid,
                    min_notice_days=notice,
                    description=description,
                )
            )
    db.flush()


def _sync_counters(db: Session) -> None:
    mapping = [
        ("employee", Employee),
        ("team", Team),
        ("skill", Skill),
        ("assignment", ShiftAssignment),
        ("leave", LeaveRequest),
        ("swap", SwapRequest),
        ("run", SchedulingRun),
        ("issue", SchedulingException),
        ("user", User),
        ("attendance", AttendanceEvent),
    ]
    for key, model in mapping:
        count = db.execute(select(func.count()).select_from(model)).scalar_one()
        ensure_counter(db, key, int(count) + 1)


def bootstrap(db: Session) -> dict:
    roles = _seed_roles(db)
    _seed_policies(db)
    ensure_defaults(db)

    employees = list(
        db.execute(select(Employee).where(Employee.status == "ACTIVE").order_by(Employee.employee_id))
        .scalars()
        .all()
    )
    # The demo employee owns EMP-000001, so the demo manager and HR user must
    # use different employee records: users.employee_id is unique.
    employee_demo = db.get(Employee, "EMP-000001") or (employees[0] if employees else None)
    excluded = {employee_demo.employee_id} if employee_demo else set()
    manager_employee = _first_manager_employee(db, excluded)
    if manager_employee:
        excluded.add(manager_employee.employee_id)
    hr_employee = next(
        (e for e in employees if e.employee_id not in excluded),
        None,
    )

    created_users = 0
    for user_id, username, email, password, role_name, employee_ref in DEMO_USERS:
        if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
            continue
        employee_id = None
        if employee_ref == "MANAGER_EMPLOYEE":
            employee_id = manager_employee.employee_id if manager_employee else None
        elif employee_ref == "HR_EMPLOYEE":
            employee_id = hr_employee.employee_id if hr_employee else None
        elif employee_ref:
            employee_id = employee_ref if db.get(Employee, employee_ref) else None
        # Do not create demo employee-linked users when no data has been loaded.
        if role_name in {RoleName.MANAGER, RoleName.HR, RoleName.EMPLOYEE} and employee_id is None:
            continue
        if employee_id and db.execute(
            select(User).where(User.employee_id == employee_id)
        ).scalar_one_or_none():
            continue
        role = roles[role_name.value]
        db.add(
            User(
                user_id=user_id,
                username=username,
                email=email,
                password_hash=hash_password(password),
                role_id=role.role_id,
                employee_id=employee_id,
                is_active=True,
            )
        )
        created_users += 1
    db.flush()
    _sync_counters(db)
    db.commit()
    return {
        "roles": len(roles),
        "employees": len(employees),
        "users_created": created_users,
        "manager_user_linked": bool(manager_employee),
    }
