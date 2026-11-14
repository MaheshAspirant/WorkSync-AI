"""Shared pytest fixtures: isolated SQLite database, seeded minimal workforce, API client."""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api.deps import db_session  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models.attendance import EmployeeAvailability  # noqa: E402
from app.models.auth import Role, User  # noqa: E402
from app.models.enums import RoleName  # noqa: E402
from app.models.leave import LeaveRequest  # noqa: E402
from app.models.master import (  # noqa: E402
    Employee,
    EmployeeSkill,
    Shift,
    ShiftTemplate,
    Skill,
    Team,
    TeamManager,
)
from app.models.scheduling import CoverageRequirement, ShiftAssignment  # noqa: E402
from app.core.ids import ensure_counter  # noqa: E402
from app.seed.bootstrap import bootstrap  # noqa: E402

TEST_PASSWORD = "Test@1234"
TEST_HASH = hash_password(TEST_PASSWORD)
ADMIN_PASSWORD = "Admin@123"


def _engine_for(path: Path):
    engine = create_engine(f"sqlite:///{path.as_posix()}", future=True,
                           connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def _seed(db):
    bootstrap(db)
    roles = {role.name: role for role in db.query(Role).all()}

    team = Team(team_id="TEAM-001", name="Operations Test", department="Operations",
                site="Bengaluru", timezone="Asia/Kolkata", is_active=True)
    team2 = Team(team_id="TEAM-002", name="Support Test", department="Customer Care",
                 site="Hyderabad", timezone="Asia/Kolkata", is_active=True)
    db.add_all([team, team2])
    db.flush()

    skills = [
        Skill(skill_id="SKL-001", name="Customer Handling", category="Customer Service"),
        Skill(skill_id="SKL-002", name="Data Entry", category="Systems"),
        Skill(skill_id="SKL-003", name="Network Support", category="Technology"),
    ]
    db.add_all(skills)
    db.flush()

    templates = [
        ShiftTemplate(shift_template_id="TPL-001", code="A", name="Morning", start_time=time(6, 0),
                      end_time=time(14, 0), duration_hours=8, crosses_midnight=False),
        ShiftTemplate(shift_template_id="TPL-002", code="B", name="Evening", start_time=time(14, 0),
                      end_time=time(22, 0), duration_hours=8, crosses_midnight=False),
        ShiftTemplate(shift_template_id="TPL-003", code="C", name="Night", start_time=time(22, 0),
                      end_time=time(6, 0), duration_hours=8, crosses_midnight=True),
    ]
    db.add_all(templates)
    db.flush()

    employees = []
    for index in range(1, 10):
        team_id = "TEAM-001" if index <= 7 else "TEAM-002"
        employee = Employee(
            employee_id=f"EMP-{index:06d}",
            team_id=team_id,
            first_name=f"Test{index}",
            last_name="Employee",
            email=f"test{index}@worksync.ai",
            job_title="Associate",
            hire_date=date(2024, 1, 1),
            status="ACTIVE",
            weekly_hours_cap=40,
            daily_hours_cap=8,
            overtime_cap_weekly=10,
            min_rest_hours=11,
            preferred_shift="NONE",
        )
        employees.append(employee)
        db.add(employee)
    db.flush()

    for index, employee in enumerate(employees, start=1):
        if employee.team_id == "TEAM-001":
            skill_ids = ["SKL-001", "SKL-002"]
        else:
            skill_ids = ["SKL-003"]
        for skill_id in skill_ids:
            db.add(EmployeeSkill(employee_id=employee.employee_id, skill_id=skill_id,
                                 proficiency=4, certified=True, years_experience=3))
        for day in range(7):
            db.add(EmployeeAvailability(employee_id=employee.employee_id, day_of_week=day,
                                        is_available=True, available_from=time(0, 0),
                                        available_to=time(23, 59), effective_from=date(2025, 1, 1)))

    db.add(TeamManager(team_id="TEAM-001", employee_id="EMP-000001", is_primary=True,
                       effective_from=date(2025, 1, 1)))

    # Coverage: two staff and one holder of each T1 skill per morning shift.
    coverage_counter = 0
    for team_id, skill_ids, required in [
        ("TEAM-001", ["SKL-001", "SKL-002"], 2),
        ("TEAM-002", ["SKL-003"], 1),
    ]:
        for template in templates:
            coverage_counter += 1
            db.add(CoverageRequirement(coverage_id=f"CVR-{coverage_counter:04d}",
                                       team_id=team_id, shift_template_id=template.shift_template_id,
                                       skill_id=None, day_type="ALL", min_staff=required,
                                       effective_from=date(2026, 1, 1)))
            for skill_id in skill_ids:
                coverage_counter += 1
                db.add(CoverageRequirement(coverage_id=f"CVR-{coverage_counter:04d}",
                                           team_id=team_id, shift_template_id=template.shift_template_id,
                                           skill_id=skill_id, day_type="ALL", min_staff=1,
                                           effective_from=date(2026, 1, 1)))

    def add_shift(shift_id, team_id, template, day, required=2):
        start = datetime.combine(day, template.start_time)
        end = datetime.combine(day + (timedelta(days=1) if template.crosses_midnight else timedelta()),
                               template.end_time)
        db.add(Shift(shift_id=shift_id, shift_date=day, shift_template_id=template.shift_template_id,
                     team_id=team_id, start_at=start, end_at=end, required_staff=required,
                     status="PUBLISHED" if day >= date(2026, 11, 14) else "COMPLETED"))

    future = date(2027, 1, 5)
    add_shift("SHIFT-2027-01-05-001-A", "TEAM-001", templates[0], future)
    add_shift("SHIFT-2027-01-05-001-B", "TEAM-001", templates[1], future)
    add_shift("SHIFT-2027-01-05-001-C", "TEAM-001", templates[2], future)
    future2 = date(2027, 1, 6)
    add_shift("SHIFT-2027-01-06-001-A", "TEAM-001", templates[0], future2, required=2)
    add_shift("SHIFT-2027-01-06-001-B", "TEAM-001", templates[1], future2, required=2)
    add_shift("SHIFT-2027-01-05-002-A", "TEAM-002", templates[0], future, required=1)
    past = date(2026, 11, 10)
    add_shift("SHIFT-2026-11-10-001-A", "TEAM-001", templates[0], past, required=1)
    db.flush()

    db.add_all([
        ShiftAssignment(assignment_id="ASG-000001", shift_id="SHIFT-2026-11-10-001-A",
                        employee_id="EMP-000002", status="COMPLETED", assignment_source="BASELINE",
                        scheduled_hours=8, assigned_at=datetime(2026, 11, 1, 9, 0)),
        ShiftAssignment(assignment_id="ASG-000002", shift_id="SHIFT-2027-01-06-001-A",
                        employee_id="EMP-000002", status="SCHEDULED", assignment_source="BASELINE",
                        scheduled_hours=8, assigned_at=datetime(2026, 12, 1, 9, 0)),
        ShiftAssignment(assignment_id="ASG-000003", shift_id="SHIFT-2027-01-06-001-B",
                        employee_id="EMP-000004", status="SCHEDULED", assignment_source="BASELINE",
                        scheduled_hours=8, assigned_at=datetime(2026, 12, 1, 9, 0)),
    ])

    users = [
        ("USR-000010", "manager", "manager.test@worksync.ai", "EMP-000001", RoleName.MANAGER),
        ("USR-000011", "employee", "employee.test@worksync.ai", "EMP-000002", RoleName.EMPLOYEE),
        ("USR-000012", "hr", "hr.test@worksync.ai", "EMP-000003", RoleName.HR),
        ("USR-000013", "target", "target.test@worksync.ai", "EMP-000004", RoleName.EMPLOYEE),
    ]
    for user_id, username, email, employee_id, role_name in users:
        db.add(User(user_id=user_id, username=username, email=email, password_hash=TEST_HASH,
                    role_id=roles[role_name].role_id, employee_id=employee_id, is_active=True))

    for key in ("assignment", "leave", "swap", "run", "issue"):
        ensure_counter(db, key, 1000)
    db.commit()


@pytest.fixture()
def app_env():
    import uuid

    temp_dir = Path(__file__).resolve().parent / "_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"worksync_test_{uuid.uuid4().hex[:8]}.db"
    engine = _engine_for(db_path)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with TestSession() as db:
        _seed(db)

    def override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_session] = override
    client = TestClient(app)
    yield {"client": client, "session": TestSession, "engine": engine}
    app.dependency_overrides.clear()
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        try:
            Path(str(db_path) + suffix).unlink(missing_ok=True)
        except OSError:
            pass


@pytest.fixture()
def client(app_env):
    return app_env["client"]


def login(client: TestClient, username: str, password: str = TEST_PASSWORD) -> dict:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def admin_headers(client):
    return login(client, "admin", ADMIN_PASSWORD)


@pytest.fixture()
def manager_headers(client):
    return login(client, "manager")


@pytest.fixture()
def employee_headers(client):
    return login(client, "employee")


@pytest.fixture()
def hr_headers(client):
    return login(client, "hr")


@pytest.fixture()
def target_headers(client):
    return login(client, "target")
