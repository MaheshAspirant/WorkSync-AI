"""Employee, team, skill, availability and reference-data endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    db_session,
    get_current_user,
    require_roles,
)
from app.models.auth import User
from app.models.enums import EmployeeStatus, RoleName
from app.schemas.common import Message, Page
from app.schemas.employees import (
    AvailabilityCreate,
    AvailabilityOut,
    EmployeeCreate,
    EmployeeOut,
    EmployeeSkillIn,
    EmployeeUpdate,
    HolidayOut,
    ShiftTemplateOut,
    SkillCreate,
    SkillOut,
    TeamCreate,
    TeamOut,
    TeamUpdate,
)
from app.services import employee_service

router = APIRouter(tags=["Employees & Organisation"])

HR_ADMIN = (RoleName.HR, RoleName.ADMIN)
MGR_HR_ADMIN = (RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)


@router.get("/employees", response_model=Page[EmployeeOut])
def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str | None = None,
    team_id: str | None = None,
    status_filter: EmployeeStatus | None = Query(None, alias="status"),
    skill_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    rows, total = employee_service.list_employees(
        db, user, page=page, page_size=page_size, q=q, team_id=team_id,
        status=status_filter, skill_id=skill_id,
    )
    return Page.build(rows, total, page, page_size)


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    user: User = Depends(require_roles(*MGR_HR_ADMIN)),
    db: Session = Depends(db_session),
):
    return employee_service.create_employee(db, user, payload)


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    employee = employee_service.get_employee(db, employee_id)
    employee_service.assert_employee_access(db, user, employee)
    return employee


@router.put("/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    user: User = Depends(require_roles(*HR_ADMIN)),
    db: Session = Depends(db_session),
):
    return employee_service.update_employee(db, user, employee_id, payload)


@router.delete("/employees/{employee_id}", response_model=Message)
def deactivate_employee(
    employee_id: str,
    user: User = Depends(require_roles(*HR_ADMIN)),
    db: Session = Depends(db_session),
):
    employee_service.deactivate_employee(db, user, employee_id)
    return {"message": "Employee deactivated; historical records preserved"}


@router.put("/employees/{employee_id}/skills", response_model=EmployeeOut)
def set_skills(
    employee_id: str,
    payload: list[EmployeeSkillIn],
    user: User = Depends(require_roles(*HR_ADMIN)),
    db: Session = Depends(db_session),
):
    return employee_service.set_employee_skills(
        db, user, employee_id, [p.model_dump() for p in payload]
    )


@router.get("/employees/{employee_id}/availability", response_model=list[AvailabilityOut])
def get_availability(
    employee_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    employee = employee_service.get_employee(db, employee_id)
    employee_service.assert_employee_access(db, user, employee)
    return employee_service.list_availability(db, employee_id)


@router.post("/employees/{employee_id}/availability", response_model=AvailabilityOut,
             status_code=status.HTTP_201_CREATED)
def set_availability(
    employee_id: str,
    payload: AvailabilityCreate,
    user: User = Depends(require_roles(*MGR_HR_ADMIN)),
    db: Session = Depends(db_session),
):
    return employee_service.upsert_availability(db, user, employee_id, payload)


@router.get("/teams", response_model=Page[TeamOut])
def list_teams(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    rows = employee_service.team_rows(db)
    from app.api.deps import managed_team_ids
    from app.models.master import Employee

    if user.role_value == RoleName.MANAGER:
        allowed = set(managed_team_ids(db, user))
        rows = [r for r in rows if r["team_id"] in allowed]
    elif user.role_value == RoleName.EMPLOYEE and user.employee_id:
        employee = db.get(Employee, user.employee_id)
        rows = [r for r in rows if r["team_id"] == (employee.team_id if employee else None)]
    if q:
        like = q.lower()
        rows = [r for r in rows if like in r["name"].lower() or like in r["department"].lower()]
    total = len(rows)
    return Page.build(rows[(page - 1) * page_size: page * page_size], total, page, page_size)


@router.post("/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    user: User = Depends(require_roles(*HR_ADMIN)),
    db: Session = Depends(db_session),
):
    team = employee_service.create_team(db, user, payload)
    return next(r for r in employee_service.team_rows(db) if r["team_id"] == team.team_id)


@router.put("/teams/{team_id}", response_model=TeamOut)
def update_team(
    team_id: str,
    payload: TeamUpdate,
    user: User = Depends(require_roles(*HR_ADMIN)),
    db: Session = Depends(db_session),
):
    team = employee_service.update_team(db, user, team_id, payload)
    return next(r for r in employee_service.team_rows(db) if r["team_id"] == team.team_id)


@router.get("/skills", response_model=Page[SkillOut])
def list_skills(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    rows = employee_service.skill_rows(db)
    total = len(rows)
    return Page.build(rows[(page - 1) * page_size: page * page_size], total, page, page_size)


@router.post("/skills", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
def create_skill(
    payload: SkillCreate,
    user: User = Depends(require_roles(*HR_ADMIN)),
    db: Session = Depends(db_session),
):
    skill = employee_service.create_skill(db, user, payload)
    return next(r for r in employee_service.skill_rows(db) if r["skill_id"] == skill.skill_id)


@router.get("/shift-templates", response_model=list[ShiftTemplateOut])
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(db_session)):
    return employee_service.list_templates(db)


@router.get("/holidays", response_model=list[HolidayOut])
def list_holidays(
    year: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    return employee_service.list_holidays(db, year)
