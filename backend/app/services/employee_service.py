"""Employee, team, skill, availability and reference-data services."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.audit.service import record_audit
from app.api.deps import managed_team_ids
from app.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.ids import next_id
from app.models.attendance import EmployeeAvailability
from app.models.auth import User
from app.models.enums import EmployeeStatus, RoleName
from app.models.master import (
    Employee,
    EmployeeSkill,
    HolidayCalendar,
    ShiftTemplate,
    Skill,
    Team,
    TeamManager,
)
from app.schemas.employees import EmployeeCreate, EmployeeUpdate, TeamCreate, TeamUpdate


def _employee_stmt():
    return select(Employee).options(
        joinedload(Employee.team),
        selectinload(Employee.skills).joinedload(EmployeeSkill.skill),
    )


def _visible_team_ids(db: Session, user: User) -> list[str] | None:
    """None means unrestricted; a list limits the query."""
    role = user.role_value
    if role in {RoleName.ADMIN, RoleName.HR}:
        return None
    if role == RoleName.MANAGER:
        return managed_team_ids(db, user)
    if role == RoleName.EMPLOYEE and user.employee_id:
        employee = db.get(Employee, user.employee_id)
        return [employee.team_id] if employee else []
    return []


def list_employees(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    team_id: str | None = None,
    status: EmployeeStatus | None = None,
    skill_id: str | None = None,
) -> tuple[list[Employee], int]:
    stmt = _employee_stmt()
    visible = _visible_team_ids(db, user)
    if visible is not None:
        if not visible:
            return [], 0
        stmt = stmt.where(Employee.team_id.in_(visible))
    if team_id:
        if visible is not None and team_id not in visible:
            raise PermissionDeniedError("You do not have access to this team")
        stmt = stmt.where(Employee.team_id == team_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Employee.first_name.ilike(like),
                Employee.last_name.ilike(like),
                Employee.email.ilike(like),
                Employee.employee_id.ilike(like),
            )
        )
    if status:
        stmt = stmt.where(Employee.status == status)
    if skill_id:
        stmt = stmt.join(EmployeeSkill).where(EmployeeSkill.skill_id == skill_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(Employee.employee_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars()
    )
    return rows, total


def get_employee(db: Session, employee_id: str) -> Employee:
    employee = db.execute(
        _employee_stmt().where(Employee.employee_id == employee_id)
    ).unique().scalar_one_or_none()
    if employee is None:
        raise NotFoundError("Employee not found")
    return employee


def assert_employee_access(db: Session, user: User, employee: Employee) -> None:
    role = user.role_value
    if role in {RoleName.ADMIN, RoleName.HR}:
        return
    if role == RoleName.MANAGER and employee.team_id in managed_team_ids(db, user):
        return
    if role == RoleName.EMPLOYEE and user.employee_id == employee.employee_id:
        return
    raise PermissionDeniedError("You do not have access to this employee")


def create_employee(db: Session, actor: User, payload: EmployeeCreate) -> Employee:
    if db.get(Team, payload.team_id) is None:
        raise NotFoundError("Team not found")
    if db.execute(select(Employee).where(Employee.email == payload.email)).scalar_one_or_none():
        raise ConflictError("An employee with this email already exists")
    skill_ids = {s.skill_id for s in payload.skills}
    if skill_ids:
        found = set(db.execute(select(Skill.skill_id).where(Skill.skill_id.in_(skill_ids))).scalars())
        missing = skill_ids - found
        if missing:
            raise ValidationError(f"Unknown skills: {sorted(missing)}")
    employee = Employee(
        employee_id=next_id(db, "employee", "EMP", 6),
        team_id=payload.team_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        job_title=payload.job_title,
        employment_type=payload.employment_type,
        hire_date=payload.hire_date,
        status=EmployeeStatus.ACTIVE,
        weekly_hours_cap=payload.weekly_hours_cap,
        daily_hours_cap=payload.daily_hours_cap,
        overtime_cap_weekly=payload.overtime_cap_weekly,
        min_rest_hours=payload.min_rest_hours,
        preferred_shift=payload.preferred_shift,
    )
    db.add(employee)
    for item in payload.skills:
        db.add(
            EmployeeSkill(
                employee_id=employee.employee_id,
                skill_id=item.skill_id,
                proficiency=item.proficiency,
                certified=item.certified,
                years_experience=item.years_experience,
            )
        )
    record_audit(db, actor, "CREATE_EMPLOYEE", "Employee", employee.employee_id,
                 new={"employee_id": employee.employee_id, "team_id": payload.team_id,
                      "email": str(payload.email)})
    db.commit()
    return get_employee(db, employee.employee_id)


def update_employee(db: Session, actor: User, employee_id: str, payload: EmployeeUpdate) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise NotFoundError("Employee not found")
    previous = {
        "team_id": employee.team_id,
        "job_title": employee.job_title,
        "status": employee.status.value,
        "email": employee.email,
        "weekly_hours_cap": employee.weekly_hours_cap,
        "preferred_shift": employee.preferred_shift.value,
    }
    data = payload.model_dump(exclude_unset=True)
    if "team_id" in data and data["team_id"]:
        if db.get(Team, data["team_id"]) is None:
            raise NotFoundError("Team not found")
    if "email" in data and data["email"]:
        existing = db.execute(select(Employee).where(Employee.email == data["email"])).scalar_one_or_none()
        if existing and existing.employee_id != employee_id:
            raise ConflictError("An employee with this email already exists")
        employee.email = str(data.pop("email"))
    for field, value in data.items():
        if value is not None:
            setattr(employee, field, value)
    record_audit(db, actor, "UPDATE_EMPLOYEE", "Employee", employee_id, previous=previous,
                 new={
                     "team_id": employee.team_id,
                     "job_title": employee.job_title,
                     "status": employee.status.value,
                     "email": employee.email,
                     "weekly_hours_cap": employee.weekly_hours_cap,
                     "preferred_shift": employee.preferred_shift.value,
                 })
    db.commit()
    return get_employee(db, employee_id)


def set_employee_skills(db: Session, actor: User, employee_id: str, skills: list[dict]) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise NotFoundError("Employee not found")
    skill_ids = {s["skill_id"] for s in skills}
    found = set(db.execute(select(Skill.skill_id).where(Skill.skill_id.in_(skill_ids))).scalars())
    missing = skill_ids - found
    if missing:
        raise ValidationError(f"Unknown skills: {sorted(missing)}")
    previous = [{"skill_id": es.skill_id, "proficiency": es.proficiency} for es in employee.skills]
    for existing in list(employee.skills):
        db.delete(existing)
    db.flush()
    for item in skills:
        db.add(
            EmployeeSkill(
                employee_id=employee_id,
                skill_id=item["skill_id"],
                proficiency=item.get("proficiency", 3),
                certified=item.get("certified", False),
                years_experience=item.get("years_experience", 0),
            )
        )
    record_audit(db, actor, "UPDATE_EMPLOYEE_SKILLS", "Employee", employee_id,
                 previous=previous, new=skills)
    db.commit()
    return get_employee(db, employee_id)


def deactivate_employee(db: Session, actor: User, employee_id: str) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise NotFoundError("Employee not found")
    previous = {"status": employee.status.value}
    employee.status = EmployeeStatus.TERMINATED
    record_audit(db, actor, "DEACTIVATE_EMPLOYEE", "Employee", employee_id,
                 previous=previous, new={"status": employee.status.value},
                 reason="Soft delete - history preserved")
    db.commit()
    return get_employee(db, employee_id)


# --------------------------------------------------------------------------- teams


def team_rows(db: Session) -> list[dict]:
    headcounts = dict(
        db.execute(select(Employee.team_id, func.count()).group_by(Employee.team_id)).all()
    )
    today = date.today()
    manager_rows = db.execute(
        select(TeamManager.team_id, Employee.first_name, Employee.last_name)
        .join(Employee, Employee.employee_id == TeamManager.employee_id)
        .where(
            TeamManager.is_primary.is_(True),
            TeamManager.effective_from <= today,
            (TeamManager.effective_to.is_(None)) | (TeamManager.effective_to >= today),
        )
    ).all()
    managers = {r[0]: f"{r[1]} {r[2]}" for r in manager_rows}
    data = []
    for team in db.execute(select(Team).order_by(Team.team_id)).scalars():
        data.append(
            {
                "team_id": team.team_id,
                "name": team.name,
                "department": team.department,
                "site": team.site,
                "cost_center": team.cost_center,
                "timezone": team.timezone,
                "is_active": team.is_active,
                "headcount": headcounts.get(team.team_id, 0),
                "manager_name": managers.get(team.team_id),
            }
        )
    return data


def create_team(db: Session, actor: User, payload: TeamCreate) -> Team:
    if db.execute(select(Team).where(Team.name == payload.name)).scalar_one_or_none():
        raise ConflictError("A team with this name already exists")
    if payload.manager_employee_id:
        if db.get(Employee, payload.manager_employee_id) is None:
            raise NotFoundError("Manager employee not found")
    team = Team(
        team_id=next_id(db, "team", "TEAM", 3),
        name=payload.name,
        department=payload.department,
        site=payload.site,
        cost_center=payload.cost_center,
        timezone=payload.timezone,
        is_active=True,
    )
    db.add(team)
    if payload.manager_employee_id:
        db.add(
            TeamManager(
                team_id=team.team_id,
                employee_id=payload.manager_employee_id,
                is_primary=True,
                effective_from=date.today(),
            )
        )
    record_audit(db, actor, "CREATE_TEAM", "Team", team.team_id,
                 new={"name": team.name, "department": team.department})
    db.commit()
    db.refresh(team)
    return team


def update_team(db: Session, actor: User, team_id: str, payload: TeamUpdate) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise NotFoundError("Team not found")
    previous = {"name": team.name, "department": team.department, "is_active": team.is_active}
    data = payload.model_dump(exclude_unset=True)
    manager_id = data.pop("manager_employee_id", None)
    for field, value in data.items():
        if value is not None:
            setattr(team, field, value)
    if manager_id:
        today = date.today()
        active = db.execute(
            select(TeamManager).where(
                TeamManager.team_id == team_id,
                TeamManager.is_primary.is_(True),
                TeamManager.effective_to.is_(None),
            )
        ).scalars()
        for row in active:
            row.effective_to = today
        db.add(
            TeamManager(
                team_id=team_id,
                employee_id=manager_id,
                is_primary=True,
                effective_from=today,
            )
        )
    record_audit(db, actor, "UPDATE_TEAM", "Team", team_id, previous=previous,
                 new={"name": team.name, "department": team.department, "is_active": team.is_active})
    db.commit()
    db.refresh(team)
    return team


# --------------------------------------------------------------------------- skills


def skill_rows(db: Session) -> list[dict]:
    counts = dict(
        db.execute(
            select(EmployeeSkill.skill_id, func.count()).group_by(EmployeeSkill.skill_id)
        ).all()
    )
    return [
        {
            "skill_id": skill.skill_id,
            "name": skill.name,
            "category": skill.category,
            "description": skill.description,
            "is_critical": skill.is_critical,
            "employee_count": counts.get(skill.skill_id, 0),
        }
        for skill in db.execute(select(Skill).order_by(Skill.skill_id)).scalars()
    ]


def create_skill(db: Session, actor: User, payload) -> Skill:
    if db.execute(select(Skill).where(Skill.name == payload.name)).scalar_one_or_none():
        raise ConflictError("A skill with this name already exists")
    skill = Skill(
        skill_id=next_id(db, "skill", "SKL", 3),
        name=payload.name,
        category=payload.category,
        description=payload.description,
        is_critical=payload.is_critical,
    )
    db.add(skill)
    record_audit(db, actor, "CREATE_SKILL", "Skill", skill.skill_id, new={"name": skill.name})
    db.commit()
    db.refresh(skill)
    return skill


def list_templates(db: Session) -> list[ShiftTemplate]:
    return list(db.execute(select(ShiftTemplate).order_by(ShiftTemplate.code)).scalars())


def list_holidays(db: Session, year: int | None = None) -> list[HolidayCalendar]:
    stmt = select(HolidayCalendar)
    if year:
        stmt = stmt.where(HolidayCalendar.holiday_date >= date(year, 1, 1),
                          HolidayCalendar.holiday_date <= date(year, 12, 31))
    return list(db.execute(stmt.order_by(HolidayCalendar.holiday_date)).scalars())


# --------------------------------------------------------------------- availability


def list_availability(db: Session, employee_id: str) -> list[EmployeeAvailability]:
    return list(
        db.execute(
            select(EmployeeAvailability)
            .where(EmployeeAvailability.employee_id == employee_id)
            .order_by(EmployeeAvailability.day_of_week)
        ).scalars()
    )


def upsert_availability(db: Session, actor: User, employee_id: str, payload) -> EmployeeAvailability:
    if db.get(Employee, employee_id) is None:
        raise NotFoundError("Employee not found")
    if payload.available_from >= payload.available_to:
        raise ValidationError("available_from must be earlier than available_to")
    existing = db.execute(
        select(EmployeeAvailability).where(
            EmployeeAvailability.employee_id == employee_id,
            EmployeeAvailability.day_of_week == payload.day_of_week,
            EmployeeAvailability.effective_from == payload.effective_from,
        )
    ).scalar_one_or_none()
    if existing:
        existing.is_available = payload.is_available
        existing.available_from = payload.available_from
        existing.available_to = payload.available_to
        existing.effective_to = payload.effective_to
        row = existing
        action = "UPDATE_AVAILABILITY"
    else:
        row = EmployeeAvailability(
            employee_id=employee_id,
            day_of_week=payload.day_of_week,
            is_available=payload.is_available,
            available_from=payload.available_from,
            available_to=payload.available_to,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
        )
        db.add(row)
        action = "CREATE_AVAILABILITY"
    record_audit(db, actor, action, "EmployeeAvailability", employee_id,
                 new={"day_of_week": payload.day_of_week, "is_available": payload.is_available})
    db.commit()
    db.refresh(row)
    return row
