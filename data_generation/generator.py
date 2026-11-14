"""Deterministic synthetic workforce data generator for WorkSync AI.

Everything is generated from a fixed seed using plain Python randomness and
Faker.  Parent/master records are produced before dependent records, all
foreign keys reference generated parents, and derived values (leave days,
attendance hours, overtime, coverage) are calculated rather than randomised.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker
from sqlalchemy import create_engine, event, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.base import Base  # noqa: E402
from app.models import (  # noqa: E402,F401  (import all models so metadata is complete)
    AttendanceEvent,
    AuditLog,
    CoverageRequirement,
    Employee,
    EmployeeAvailability,
    EmployeeSkill,
    HolidayCalendar,
    IdCounter,
    LeaveApprovalHistory,
    LeavePolicy,
    LeaveRequest,
    Role,
    SchedulingDecision,
    SchedulingException,
    SchedulingRun,
    Shift,
    ShiftAssignment,
    ShiftTemplate,
    Skill,
    SwapApprovalHistory,
    SwapRequest,
    SystemConfig,
    Team,
    TeamManager,
    User,
)
from data_generation.config import GenerationConfig  # noqa: E402

TABLE_ORDER = [
    "teams",
    "skills",
    "employees",
    "employee_skills",
    "employee_availability",
    "team_managers",
    "shift_templates",
    "coverage_requirements",
    "holiday_calendar",
    "leave_policies",
    "leave_requests",
    "leave_approval_history",
    "shifts",
    "shift_assignments",
    "attendance_events",
    "swap_requests",
    "swap_approval_history",
]

MASTER_TABLES = {
    "teams", "skills", "employees", "employee_skills", "employee_availability",
    "team_managers", "shift_templates", "coverage_requirements", "holiday_calendar",
    "leave_policies",
}

SKILL_POOL = [
    ("Customer Handling", "Customer Service", False),
    ("POS Operation", "Retail", False),
    ("Inventory Management", "Logistics", False),
    ("Forklift Operation", "Logistics", True),
    ("First Aid", "Safety", True),
    ("Fire Safety", "Safety", True),
    ("Quality Inspection", "Quality", False),
    ("Data Entry", "Systems", False),
    ("Excel Reporting", "Systems", False),
    ("SQL Reporting", "Systems", False),
    ("Network Support", "Technology", False),
    ("Hardware Repair", "Technology", False),
    ("Food Safety", "Compliance", True),
    ("Manual Handling", "Safety", False),
    ("Team Leadership", "Leadership", False),
    ("Conflict Resolution", "Customer Service", False),
    ("Hindi Communication", "Language", False),
    ("English Communication", "Language", False),
    ("SAP", "Systems", False),
    ("Warehouse Management", "Logistics", False),
    ("Payments Reconciliation", "Finance", False),
    ("Fraud Screening", "Compliance", True),
    ("Chat Support", "Customer Service", False),
    ("Vendor Coordination", "Operations", False),
]

DEPARTMENTS = [
    ("Operations", "Bengaluru"),
    ("Customer Care", "Hyderabad"),
    ("Logistics", "Pune"),
    ("Retail", "Mumbai"),
    ("Fulfilment", "Chennai"),
    ("Technical Support", "Bengaluru"),
    ("Quality", "Pune"),
    ("Finance Operations", "Hyderabad"),
]

JOB_TITLES = {
    "Operations": "Operations Associate",
    "Customer Care": "Customer Support Executive",
    "Logistics": "Logistics Associate",
    "Retail": "Retail Associate",
    "Fulfilment": "Fulfilment Associate",
    "Technical Support": "Support Engineer",
    "Quality": "Quality Analyst",
    "Finance Operations": "Finance Associate",
}

LEAVE_POLICIES = [
    ("POL-001", "ANNUAL", 20, 15, None, True, 7),
    ("POL-002", "SICK", 10, 5, 2, True, 0),
    ("POL-003", "UNPAID", 30, 30, None, False, 3),
    ("POL-004", "PARENTAL", 90, 90, 1, True, 30),
    ("POL-005", "BEREAVEMENT", 5, 5, None, True, 0),
]

LEAVE_REASONS = {
    "ANNUAL": ["Family holiday", "Planned vacation", "Personal time off", "Travel"],
    "SICK": ["Fever and rest advised", "Medical appointment", "Flu recovery", "Dental procedure"],
    "UNPAID": ["Personal errand", "Family commitment", "Relocation", "Extended break"],
    "PARENTAL": ["Parental leave", "Childcare", "Adoption leave"],
    "BEREAVEMENT": ["Family bereavement", "Compassionate leave"],
}

TEMPLATES = [
    ("TPL-001", "A", "Morning", time(6, 0), time(14, 0), 8.0, False, "#f59e0b"),
    ("TPL-002", "B", "Evening", time(14, 0), time(22, 0), 8.0, False, "#3b82f6"),
    ("TPL-003", "C", "Night", time(22, 0), time(6, 0), 8.0, True, "#6366f1"),
]

HOLIDAYS = [
    (date(2026, 10, 2), "Gandhi Jayanti"),
    (date(2026, 10, 20), "Dussehra"),
    (date(2026, 11, 8), "Diwali"),
    (date(2026, 11, 24), "Guru Nanak Jayanti"),
    (date(2026, 12, 25), "Christmas Day"),
]

ACTIVE_STATUSES = {"SCHEDULED", "CONFIRMED", "COMPLETED", "SWAPPED_IN"}


class DataGenerator:
    def __init__(self, config: GenerationConfig):
        self.cfg = config
        self.rng = random.Random(config.seed)
        self.faker = Faker("en_IN")
        Faker.seed(config.seed)
        self.data: dict[str, list[dict]] = defaultdict(list)
        self.ground_truth: list[dict] = []
        self.employee_by_id: dict[str, dict] = {}
        self.team_employees: dict[str, list[str]] = defaultdict(list)
        self.team_skills: dict[str, list[str]] = {}
        self.skills_by_employee: dict[str, set[str]] = defaultdict(set)
        self.approved_leave_dates: dict[str, set[date]] = defaultdict(set)
        self.availability: dict[str, dict[int, bool]] = defaultdict(dict)
        self.required_staff: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
        self.skill_requirements: dict[str, dict[str, list[str]]] = defaultdict(dict)
        self.holiday_dates: set[date] = set()
        self.assignment_by_id: dict[str, dict] = {}
        self.shifts_by_id: dict[str, dict] = {}
        self.team_size_by_id: dict[str, int] = {}
        self._counters: dict[str, int] = defaultdict(int)
        self.unfilled_shifts: list[str] = []
        self.attendance_ids: set[str] = set()

    # ------------------------------------------------------------------ ids
    def _next(self, key: str) -> int:
        self._counters[key] += 1
        return self._counters[key]

    def _team_id(self, number: int) -> str:
        return f"TEAM-{number:03d}"

    # ---------------------------------------------------------------- dates
    def _day_type(self, day: date) -> str:
        if day in self.holiday_dates:
            return "HOLIDAY"
        if day.weekday() >= 5:
            return "WEEKEND"
        return "WEEKDAY"

    def _working_days(self, start: date, end: date) -> int:
        count = 0
        cursor = start
        while cursor <= end:
            if cursor.weekday() < 5 and cursor not in self.holiday_dates:
                count += 1
            cursor += timedelta(days=1)
        return count

    # ------------------------------------------------------------ master
    def generate_skills(self) -> None:
        for index in range(1, self.cfg.skills + 1):
            name, category, critical = SKILL_POOL[(index - 1) % len(SKILL_POOL)]
            self.data["skills"].append(
                {
                    "skill_id": f"SKL-{index:03d}",
                    "name": name,
                    "category": category,
                    "description": f"Synthetic {category.lower()} skill used for staffing coverage.",
                    "is_critical": critical,
                    "created_at": datetime(2025, 1, 1, 9, 0),
                    "updated_at": datetime(2025, 1, 1, 9, 0),
                }
            )

    def generate_teams(self) -> None:
        total = self.cfg.employees
        base = total // self.cfg.teams
        sizes = [base] * self.cfg.teams
        for index in range(self.cfg.teams - 1):
            sizes[index] = max(6, sizes[index] + self.rng.choice([-2, -1, 0, 0, 1, 2]))
        sizes[-1] = total - sum(sizes[:-1])
        if sizes[-1] < 6:
            deficit = 6 - sizes[-1]
            sizes[-1] = 6
            for index in range(self.cfg.teams - 1):
                if deficit <= 0:
                    break
                take = min(deficit, max(0, sizes[index] - 6))
                sizes[index] -= take
                deficit -= take
        self.team_size_by_id = {}
        for index, size in enumerate(sizes, start=1):
            team_id = self._team_id(index)
            department, site = DEPARTMENTS[(index - 1) % len(DEPARTMENTS)]
            team_name = f"{department} {site} {index:02d}"
            self.data["teams"].append(
                {
                    "team_id": team_id,
                    "name": team_name,
                    "department": department,
                    "site": site,
                    "cost_center": f"CC-{index:03d}",
                    "timezone": "Asia/Kolkata",
                    "is_active": True,
                    "created_at": datetime(2025, 1, 1, 8, 0),
                    "updated_at": datetime(2025, 1, 1, 8, 0),
                }
            )
            self.team_size_by_id[team_id] = size
            skill_ids = [
                f"SKL-{((index * 3 + offset) % self.cfg.skills) + 1:03d}"
                for offset in range(3)
            ]
            self.team_skills[team_id] = sorted(set(skill_ids))

    def generate_employees(self) -> None:
        sequence = 0
        skills_per_team = self.team_skills
        for team_index, team in enumerate(self.data["teams"], start=1):
            team_id = team["team_id"]
            department = team["department"]
            size = self.team_size_by_id[team_id]
            for position in range(size):
                sequence += 1
                first = self.faker.first_name()
                last = self.faker.last_name()
                email = f"{first.lower().replace(' ', '')}.{last.lower().replace(' ', '')}.{sequence}@worksync.ai"
                employment = self.rng.choices(
                    ["FULL_TIME", "PART_TIME", "CONTRACT"], weights=[82, 12, 6]
                )[0]
                weekly_cap = {"FULL_TIME": 40.0, "PART_TIME": 28.0, "CONTRACT": 40.0}[employment]
                status = self.rng.choices(
                    ["ACTIVE", "ON_LEAVE", "INACTIVE"], weights=[96, 3, 1]
                )[0]
                preferred = self.rng.choices(
                    ["MORNING", "EVENING", "NIGHT", "NONE"], weights=[30, 28, 18, 24]
                )[0]
                hire_date = date(2018, 1, 1) + timedelta(days=self.rng.randint(0, 2700))
                employee = {
                    "employee_id": f"EMP-{sequence:06d}",
                    "team_id": team_id,
                    "first_name": first,
                    "last_name": last,
                    "email": email,
                    "phone": f"+91-9{self.rng.randint(100000000, 999999999)}",
                    "job_title": JOB_TITLES.get(department, "Associate"),
                    "employment_type": employment,
                    "hire_date": hire_date,
                    "status": status,
                    "weekly_hours_cap": weekly_cap,
                    "daily_hours_cap": 8.0,
                    "overtime_cap_weekly": float(self.rng.choice([8, 10, 12])),
                    "min_rest_hours": 11.0,
                    "preferred_shift": preferred,
                    "notes": None,
                    "created_at": datetime(2025, 1, 2, 9, 0),
                    "updated_at": datetime(2025, 1, 2, 9, 0),
                }
                self.data["employees"].append(employee)
                self.employee_by_id[employee["employee_id"]] = employee
                self.team_employees[team_id].append(employee["employee_id"])

    def generate_employee_skills(self) -> None:
        for team_id, employees in self.team_employees.items():
            team_skills = self.team_skills[team_id]
            for position, employee_id in enumerate(employees):
                primary = team_skills[position % len(team_skills)]
                chosen = {primary}
                if len(team_skills) > 1:
                    extra_count = self.rng.choices([0, 1, 2], weights=[25, 50, 25])[0]
                    for candidate in self.rng.sample(team_skills, min(extra_count, len(team_skills))):
                        chosen.add(candidate)
                if self.rng.random() < 0.08:
                    global_skill = f"SKL-{self.rng.randint(1, self.cfg.skills):03d}"
                    chosen.add(global_skill)
                # Most operations employees are cross-trained on the team's
                # skills; a small specialist minority keeps skill gaps possible.
                target_known = len(team_skills) if self.rng.random() < 0.90 else max(1, len(team_skills) - 1)
                for skill_id in team_skills:
                    if len(chosen) >= target_known:
                        break
                    chosen.add(skill_id)
                for skill_id in sorted(chosen):
                    self._add_employee_skill(employee_id, skill_id)

            # Cross-training guard: every team skill must have enough holders
            # for three shifts and two days off.  Without this, a skill could be
            # held by only one or two people and coverage becomes infeasible.
            target_holders = max(6, int(round(len(employees) * 0.55)))
            for skill_id in team_skills:
                holders = [e for e in employees if skill_id in self.skills_by_employee[e]]
                if len(holders) >= target_holders:
                    continue
                candidates = [e for e in employees if skill_id not in self.skills_by_employee[e]]
                candidates.sort(key=lambda e: (len(self.skills_by_employee[e]), e))
                for employee_id in candidates[: target_holders - len(holders)]:
                    self._add_employee_skill(employee_id, skill_id)

    def _add_employee_skill(self, employee_id: str, skill_id: str) -> None:
        if skill_id in self.skills_by_employee[employee_id]:
            return
        self.skills_by_employee[employee_id].add(skill_id)
        self.data["employee_skills"].append(
            {
                "employee_id": employee_id,
                "skill_id": skill_id,
                "proficiency": self.rng.randint(2, 5),
                "certified": self.rng.random() < 0.45,
                "years_experience": round(self.rng.uniform(0.5, 12), 1),
                "updated_at": datetime(2025, 2, 1, 9, 0),
            }
        )

    def generate_team_managers(self) -> None:
        for team in self.data["teams"]:
            team_id = team["team_id"]
            employees = [e for e in self.team_employees[team_id] if self.employee_by_id[e]["status"] == "ACTIVE"]
            if not employees:
                employees = self.team_employees[team_id]
            manager_id = employees[0]
            self.employee_by_id[manager_id]["job_title"] = "Team Lead"
            self.data["team_managers"].append(
                {
                    "team_manager_id": self._next("team_manager"),
                    "team_id": team_id,
                    "employee_id": manager_id,
                    "is_primary": True,
                    "effective_from": date(2025, 1, 1),
                    "effective_to": None,
                    "created_at": datetime(2025, 1, 1, 9, 0),
                    "updated_at": datetime(2025, 1, 1, 9, 0),
                }
            )

    def generate_shift_templates(self) -> None:
        for template_id, code, name, start, end, duration, crosses, color in TEMPLATES:
            self.data["shift_templates"].append(
                {
                    "shift_template_id": template_id,
                    "code": code,
                    "name": name,
                    "start_time": start,
                    "end_time": end,
                    "duration_hours": duration,
                    "crosses_midnight": crosses,
                    "color": color,
                    "created_at": datetime(2025, 1, 1, 9, 0),
                    "updated_at": datetime(2025, 1, 1, 9, 0),
                }
            )

    def generate_coverage(self) -> None:
        for team_index, team in enumerate(self.data["teams"], start=1):
            team_id = team["team_id"]
            team_skills = self.team_skills[team_id]
            # Teams of 18-22 people cannot safely staff four people on every
            # one of three shifts, especially the night shift; 2-3 per shift is
            # the documented staffing model.
            base = 2 + (team_index % 2)
            for template_offset, template in enumerate(TEMPLATES):
                template_id, code = template[0], template[1]
                if code == "C":
                    required = {
                        "WEEKDAY": max(2, base - 1),
                        "WEEKEND": 2,
                        "HOLIDAY": 2,
                    }
                else:
                    required = {
                        "WEEKDAY": base,
                        "WEEKEND": max(2, base - 1),
                        "HOLIDAY": max(2, base - 1),
                    }
                self.required_staff[team_id][code] = required
                chosen_skills = [
                    team_skills[(template_offset + offset) % len(team_skills)]
                    for offset in range(2)
                ]
                self.skill_requirements[team_id][code] = chosen_skills
                for day_type in ("WEEKDAY", "WEEKEND", "HOLIDAY"):
                    self.data["coverage_requirements"].append(
                        {
                            "coverage_id": f"CVR-{self._next('coverage'):04d}",
                            "team_id": team_id,
                            "shift_template_id": template_id,
                            "skill_id": None,
                            "day_type": day_type,
                            "min_staff": required[day_type],
                            "effective_from": self.cfg.start_date,
                            "effective_to": None,
                            "created_at": datetime(2025, 9, 1, 9, 0),
                            "updated_at": datetime(2025, 9, 1, 9, 0),
                        }
                    )
                    for skill_id in chosen_skills:
                        self.data["coverage_requirements"].append(
                            {
                                "coverage_id": f"CVR-{self._next('coverage'):04d}",
                                "team_id": team_id,
                                "shift_template_id": template_id,
                                "skill_id": skill_id,
                                "day_type": day_type,
                                "min_staff": 1,
                                "effective_from": self.cfg.start_date,
                                "effective_to": None,
                                "created_at": datetime(2025, 9, 1, 9, 0),
                                "updated_at": datetime(2025, 9, 1, 9, 0),
                            }
                        )

    def generate_holidays(self) -> None:
        for index, (holiday_date, name) in enumerate(HOLIDAYS, start=1):
            # Keep public holidays for the whole leave horizon, not just the
            # shift window, so leave-day arithmetic is always consistent.
            self.holiday_dates.add(holiday_date)
            self.data["holiday_calendar"].append(
                {
                    "holiday_id": f"HOL-{index:03d}",
                    "holiday_date": holiday_date,
                    "name": name,
                    "region": "IN",
                    "is_paid": True,
                    "is_recurring": False,
                    "created_at": datetime(2025, 9, 1, 9, 0),
                    "updated_at": datetime(2025, 9, 1, 9, 0),
                }
            )

    def generate_leave_policies(self) -> None:
        for policy_id, leave_type, entitlement, consecutive, document_after, paid, notice in LEAVE_POLICIES:
            self.data["leave_policies"].append(
                {
                    "policy_id": policy_id,
                    "leave_type": leave_type,
                    "annual_entitlement_days": float(entitlement),
                    "max_consecutive_days": consecutive,
                    "requires_document_after_days": document_after,
                    "is_paid": paid,
                    "min_notice_days": notice,
                    "description": f"Synthetic policy for {leave_type.lower()} leave.",
                    "created_at": datetime(2025, 1, 1, 9, 0),
                    "updated_at": datetime(2025, 1, 1, 9, 0),
                }
            )

    # -------------------------------------------------------------- leaves
    def generate_leaves(self) -> None:
        active = [e for e in self.data["employees"] if e["status"] == "ACTIVE"]
        used_dates: dict[str, set[date]] = defaultdict(set)
        annual_used: dict[str, float] = defaultdict(float)
        history_id = 0
        attempts = 0
        while len(self.data["leave_requests"]) < self.cfg.leave_requests and attempts < self.cfg.leave_requests * 40:
            attempts += 1
            employee = self.rng.choice(active)
            employee_id = employee["employee_id"]
            leave_type = self.rng.choices(
                ["ANNUAL", "SICK", "UNPAID", "PARENTAL", "BEREAVEMENT"],
                weights=[45, 30, 14, 3, 8],
            )[0]
            duration = {
                "ANNUAL": self.rng.randint(1, 7),
                "SICK": self.rng.randint(1, 4),
                "UNPAID": self.rng.randint(1, 5),
                "PARENTAL": self.rng.randint(10, 30),
                "BEREAVEMENT": self.rng.randint(1, 3),
            }[leave_type]
            offset = self.rng.randint(-12, self.cfg.days + 10)
            start = self.cfg.start_date + timedelta(days=offset)
            end = start + timedelta(days=duration - 1)
            days = self._working_days(start, end)
            if days <= 0:
                continue
            if leave_type == "ANNUAL" and annual_used[employee_id] + days > 20:
                leave_type = "SICK"
                duration = min(duration, 4)
                end = start + timedelta(days=duration - 1)
                days = self._working_days(start, end)
                if days <= 0:
                    continue
            overlap = False
            cursor = start
            while cursor <= end:
                if cursor in used_dates[employee_id]:
                    overlap = True
                    break
                cursor += timedelta(days=1)
            if overlap:
                continue
            status = self.rng.choices(
                ["APPROVED", "PENDING", "REJECTED", "CANCELLED"], weights=[60, 20, 14, 6]
            )[0]
            submitted = datetime.combine(start - timedelta(days=self.rng.randint(5, 25)), time(9, 0))
            decided = submitted + timedelta(days=2) if status in {"APPROVED", "REJECTED"} else None
            leave_id = f"LVE-{start.year}-{self._next('leave'):06d}"
            self.data["leave_requests"].append(
                {
                    "leave_id": leave_id,
                    "employee_id": employee_id,
                    "policy_id": {
                        "ANNUAL": "POL-001", "SICK": "POL-002", "UNPAID": "POL-003",
                        "PARENTAL": "POL-004", "BEREAVEMENT": "POL-005",
                    }[leave_type],
                    "leave_type": leave_type,
                    "start_date": start,
                    "end_date": end,
                    "total_days": float(days),
                    "reason": self.rng.choice(LEAVE_REASONS[leave_type]),
                    "status": status,
                    "submitted_at": submitted,
                    "decided_at": decided,
                    "decided_by_user_id": None,
                    "manager_comment": {
                        "APPROVED": "Approved by team manager",
                        "REJECTED": "Rejected due to coverage requirements",
                        "CANCELLED": "Withdrawn by employee",
                    }.get(status),
                    "created_at": submitted,
                    "updated_at": decided or submitted,
                }
            )
            history_id += 1
            self.data["leave_approval_history"].append(
                {
                    "history_id": history_id,
                    "leave_id": leave_id,
                    "from_status": None,
                    "to_status": "PENDING",
                    "action": "SUBMITTED",
                    "actor_user_id": None,
                    "comment": "Submitted through employee self-service",
                    "created_at": submitted,
                }
            )
            if status in {"APPROVED", "REJECTED", "CANCELLED"}:
                history_id += 1
                self.data["leave_approval_history"].append(
                    {
                        "history_id": history_id,
                        "leave_id": leave_id,
                        "from_status": "PENDING",
                        "to_status": status,
                        "action": status,
                        "actor_user_id": None,
                        "comment": "Synthetic seed decision",
                        "created_at": decided or submitted + timedelta(days=1),
                    }
                )
            for day in (start + timedelta(days=i) for i in range((end - start).days + 1)):
                used_dates[employee_id].add(day)
                if status == "APPROVED":
                    self.approved_leave_dates[employee_id].add(day)
            if status in {"APPROVED", "PENDING"} and leave_type == "ANNUAL":
                annual_used[employee_id] += days

    # ----------------------------------------------------------- availability
    def generate_availability(self) -> None:
        # A separate RNG avoids accidental correlation between skill choice and
        # days off (which made whole skill groups unavailable on the same day).
        availability_rng = random.Random(self.cfg.seed + 99173)
        records: dict[tuple[str, int], dict] = {}
        for employee in self.data["employees"]:
            off_days = set(
                availability_rng.sample(
                    range(7), 2 if employee["employment_type"] == "FULL_TIME" else 3
                )
            )
            for day in range(7):
                available = day not in off_days
                self.availability[employee["employee_id"]][day] = available
                row = {
                    "availability_id": self._next("availability"),
                    "employee_id": employee["employee_id"],
                    "day_of_week": day,
                    "is_available": available,
                    "available_from": time(0, 0),
                    "available_to": time(23, 59),
                    "effective_from": date(2025, 1, 1),
                    "effective_to": None,
                    "created_at": datetime(2025, 1, 1, 9, 0),
                    "updated_at": datetime(2025, 1, 1, 9, 0),
                }
                records[(employee["employee_id"], day)] = row
                self.data["employee_availability"].append(row)

        # Feasibility guard: each team must have enough people, and at least two
        # holders of every team skill, available on every weekday.  This models
        # managers ensuring rosters are coverable.
        for team in self.data["teams"]:
            team_id = team["team_id"]
            employees = self.team_employees[team_id]
            for day in range(7):
                available = [e for e in employees if self.availability[e][day]]
                target = min(len(employees), 11)
                if len(available) < target:
                    for employee_id in employees:
                        if len(available) >= target:
                            break
                        if not self.availability[employee_id][day]:
                            self._make_available(records, employee_id, day)
                            available.append(employee_id)
                for skill_id in self.team_skills[team_id]:
                    holders = [
                        e for e in employees if skill_id in self.skills_by_employee[e]
                    ]
                    available_holders = [
                        e for e in holders if self.availability[e][day]
                    ]
                    if len(available_holders) < 2:
                        for employee_id in holders:
                            if len(available_holders) >= 2:
                                break
                            if not self.availability[employee_id][day]:
                                self._make_available(records, employee_id, day)
                                available_holders.append(employee_id)

    def _make_available(self, records: dict, employee_id: str, day: int) -> None:
        self.availability[employee_id][day] = True
        row = records.get((employee_id, day))
        if row:
            row["is_available"] = True
            row["updated_at"] = datetime(2025, 1, 3, 9, 0)

    # --------------------------------------------------------------- shifts
    def generate_shifts(self) -> None:
        templates = {t[1]: t for t in TEMPLATES}
        for team in self.data["teams"]:
            team_id = team["team_id"]
            team_number = int(team_id.split("-")[1])
            for day_offset in range(self.cfg.days):
                shift_date = self.cfg.start_date + timedelta(days=day_offset)
                day_type = self._day_type(shift_date)
                for template_id, code, name, start_clock, end_clock, duration, crosses, _color in TEMPLATES:
                    required = self.required_staff[team_id][code][day_type]
                    start_at = datetime.combine(shift_date, start_clock)
                    end_at = datetime.combine(
                        shift_date + timedelta(days=1) if crosses else shift_date, end_clock
                    )
                    shift_id = f"SHIFT-{shift_date.isoformat()}-{team_number:03d}-{code}"
                    status = "COMPLETED" if shift_date < self.cfg.as_of_date else "PUBLISHED"
                    shift = {
                        "shift_id": shift_id,
                        "shift_date": shift_date,
                        "shift_template_id": template_id,
                        "team_id": team_id,
                        "start_at": start_at,
                        "end_at": end_at,
                        "required_staff": required,
                        "status": status,
                        "created_at": datetime.combine(shift_date - timedelta(days=30), time(9, 0)),
                        "updated_at": datetime.combine(shift_date - timedelta(days=30), time(9, 0)),
                    }
                    self.data["shifts"].append(shift)
                    self.shifts_by_id[shift_id] = shift

    # ------------------------------------------------------------- assignment
    def generate_assignments(self) -> None:
        active_by_team: dict[str, list[str]] = defaultdict(list)
        for employee in self.data["employees"]:
            if employee["status"] == "ACTIVE":
                active_by_team[employee["team_id"]].append(employee["employee_id"])
        hours: dict[tuple[str, date], float] = defaultdict(float)
        code_counts: dict[tuple[str, str], int] = defaultdict(int)
        last_end: dict[str, datetime] = {}
        assigned_dates: dict[tuple[str, date], int] = defaultdict(int)

        # Night shifts are the scarcest resource (rest rules block the next
        # morning), so schedule them first within each day, then morning and
        # evening.  Team order is irrelevant because pools are disjoint.
        code_priority = {"C": 0, "A": 1, "B": 2}
        shifts = sorted(
            self.data["shifts"],
            key=lambda s: (
                s["start_at"].date(),
                code_priority[s["shift_id"].rsplit("-", 1)[1]],
                s["team_id"],
            ),
        )
        for shift in shifts:
            team_id = shift["team_id"]
            code = shift["shift_id"].rsplit("-", 1)[1]
            required = shift["required_staff"]
            skill_reqs = self.skill_requirements[team_id][code]
            monday = shift["start_at"].date() - timedelta(days=shift["start_at"].weekday())
            candidates: list[str] = []
            for employee_id in active_by_team[team_id]:
                if shift["start_at"].date() in self.approved_leave_dates[employee_id]:
                    continue
                if not self.availability[employee_id].get(shift["start_at"].weekday(), True):
                    continue
                if assigned_dates[(employee_id, shift["start_at"].date())] > 0:
                    continue
                if last_end.get(employee_id) and shift["start_at"] < last_end[employee_id] + timedelta(hours=11):
                    continue
                # Prefer <=40h but allow the contractual overtime allowance so
                # skill minima can still be met on constrained days.
                if hours[(employee_id, monday)] + 8 > 50:
                    continue
                candidates.append(employee_id)
            selected: list[str] = []
            for skill_id in skill_reqs:
                eligible = [e for e in candidates if skill_id in self.skills_by_employee[e] and e not in selected]
                if not eligible:
                    continue
                eligible.sort(key=lambda e: (hours[(e, monday)], code_counts[(e, code)], self.rng.random()))
                selected.append(eligible[0])
            remaining = required - len(selected)
            if remaining > 0:
                pool = [e for e in candidates if e not in selected]
                pool.sort(key=lambda e: (hours[(e, monday)], code_counts[(e, code)], self.rng.random()))
                for employee_id in pool:
                    if remaining <= 0:
                        break
                    if hours[(employee_id, monday)] + 8 > 50:
                        continue
                    selected.append(employee_id)
                    remaining -= 1
            if remaining > 0:
                self.unfilled_shifts.append(shift["shift_id"])
            for employee_id in selected:
                assignment_id = f"ASG-{self._next('assignment'):06d}"
                assignment = {
                    "assignment_id": assignment_id,
                    "shift_id": shift["shift_id"],
                    "employee_id": employee_id,
                    "status": "COMPLETED" if shift["shift_date"] < self.cfg.as_of_date else "SCHEDULED",
                    "assignment_source": "BASELINE",
                    "assigned_at": shift["start_at"] - timedelta(days=14),
                    "scheduled_hours": 8.0,
                    "is_overtime": False,
                    "run_id": None,
                    "notes": "Baseline roster generated from coverage requirements.",
                    "created_at": shift["start_at"] - timedelta(days=14),
                    "updated_at": shift["start_at"] - timedelta(days=14),
                }
                self.data["shift_assignments"].append(assignment)
                self.assignment_by_id[assignment_id] = assignment
                hours[(employee_id, monday)] += 8
                code_counts[(employee_id, code)] += 1
                assigned_dates[(employee_id, shift["shift_date"])] += 1
                last_end[employee_id] = max(
                    last_end.get(employee_id, shift["end_at"]), shift["end_at"]
                )

    # ------------------------------------------------------------- attendance
    def generate_attendance(self) -> None:
        weekly_overtime: dict[tuple[str, date], float] = defaultdict(float)
        for assignment in sorted(self.data["shift_assignments"], key=lambda a: a["assigned_at"]):
            if assignment["status"] not in ACTIVE_STATUSES:
                continue
            shift = self.shifts_by_id[assignment["shift_id"]]
            if shift["shift_date"] > self.cfg.as_of_date:
                continue
            employee = self.employee_by_id[assignment["employee_id"]]
            scheduled_start = shift["start_at"]
            scheduled_end = shift["end_at"]
            monday = shift["shift_date"] - timedelta(days=shift["shift_date"].weekday())
            outcome = self.rng.choices(
                ["PRESENT", "LATE", "EARLY", "ABSENT", "NO_SHOW"],
                weights=[84, 7, 3, 4, 2],
            )[0]
            if outcome in {"ABSENT", "NO_SHOW"}:
                check_in = check_out = None
                late_minutes = early_minutes = 0
                actual_hours = overtime = 0.0
                status = "ABSENT" if outcome == "ABSENT" else "NO_SHOW"
                created = scheduled_end + timedelta(minutes=30)
            else:
                if outcome == "EARLY":
                    check_in = scheduled_start + timedelta(minutes=self.rng.randint(-5, 5))
                    check_out = scheduled_end - timedelta(minutes=self.rng.randint(15, 60))
                else:
                    late = outcome == "LATE"
                    check_in = scheduled_start + timedelta(
                        minutes=self.rng.randint(8, 35) if late else self.rng.randint(-5, 5)
                    )
                    extra = self.rng.choices([0, 15, 30, 45, 60, 90], weights=[55, 10, 10, 10, 10, 5])[0]
                    check_out = scheduled_end + timedelta(minutes=extra)
                if check_out <= check_in + timedelta(hours=1):
                    check_out = check_in + timedelta(hours=8)
                actual_hours = round((check_out - check_in).total_seconds() / 3600, 2)
                overtime = round(max(0.0, actual_hours - 8.0), 2)
                cap = float(employee["overtime_cap_weekly"])
                if weekly_overtime[(employee["employee_id"], monday)] + overtime > cap:
                    check_out = check_in + timedelta(hours=8)
                    actual_hours = round((check_out - check_in).total_seconds() / 3600, 2)
                    overtime = round(max(0.0, actual_hours - 8.0), 2)
                weekly_overtime[(employee["employee_id"], monday)] += overtime
                late_minutes = max(0, int((check_in - scheduled_start).total_seconds() // 60))
                early_minutes = max(0, int((scheduled_end - check_out).total_seconds() // 60))
                if late_minutes > 5:
                    status = "LATE"
                elif early_minutes > 0:
                    status = "EARLY_DEPARTURE"
                else:
                    status = "PRESENT"
                created = check_out + timedelta(minutes=45)
            anchor = check_in or scheduled_start
            attendance_id = f"ATT-{assignment['employee_id']}-{anchor.strftime('%Y%m%dT%H%M%S')}"
            suffix = 1
            base_id = attendance_id
            while attendance_id in self.attendance_ids:
                suffix += 1
                attendance_id = f"{base_id}-{suffix}"
            self.attendance_ids.add(attendance_id)
            self.data["attendance_events"].append(
                {
                    "attendance_id": attendance_id,
                    "employee_id": assignment["employee_id"],
                    "shift_id": assignment["shift_id"],
                    "assignment_id": assignment["assignment_id"],
                    "scheduled_start": scheduled_start,
                    "scheduled_end": scheduled_end,
                    "actual_check_in": check_in,
                    "actual_check_out": check_out,
                    "status": status,
                    "late_minutes": late_minutes,
                    "early_departure_minutes": early_minutes,
                    "actual_hours": actual_hours,
                    "overtime_hours": overtime,
                    "source": "BIOMETRIC",
                    "reconciliation_status": "MATCHED",
                    "notes": None,
                    "created_at": created,
                    "updated_at": created,
                }
            )

    # ------------------------------------------------------------------ swaps
    def generate_swaps(self) -> None:
        assignments = [
            a for a in self.data["shift_assignments"]
            if a["status"] in {"SCHEDULED", "COMPLETED", "CONFIRMED"}
        ]
        by_team_date: dict[tuple[str, date], list[dict]] = defaultdict(list)
        assignments_by_employee: dict[str, list[dict]] = defaultdict(list)
        for assignment in assignments:
            shift = self.shifts_by_id[assignment["shift_id"]]
            by_team_date[(shift["team_id"], shift["shift_date"])].append(assignment)
            assignments_by_employee[assignment["employee_id"]].append(assignment)
        pairs = [(key, rows) for key, rows in by_team_date.items() if len(rows) >= 2]
        self.rng.shuffle(pairs)
        statuses = ["REQUESTED", "APPROVED", "APPLIED", "REJECTED", "CANCELLED"]
        weights = [25, 15, 35, 15, 10]
        history_id = 0
        attempts = 0

        def rest_safe(employee_id: str, new_shift: dict, exclude_id: str) -> bool:
            employee = self.employee_by_id[employee_id]
            if new_shift["shift_date"] in self.approved_leave_dates[employee_id]:
                return False
            if not self.availability[employee_id].get(new_shift["shift_date"].weekday(), True):
                return False
            for other in assignments_by_employee.get(employee_id, []):
                if other["assignment_id"] == exclude_id:
                    continue
                if other["shift_id"] == new_shift["shift_id"]:
                    return False
                existing = self.shifts_by_id[other["shift_id"]]
                if existing["start_at"] < new_shift["end_at"] and new_shift["start_at"] < existing["end_at"]:
                    return False
                if existing["end_at"] <= new_shift["start_at"]:
                    gap = (new_shift["start_at"] - existing["end_at"]).total_seconds() / 3600
                else:
                    gap = (existing["start_at"] - new_shift["end_at"]).total_seconds() / 3600
                if gap < 11:
                    return False
            return True

        while len(self.data["swap_requests"]) < self.cfg.swap_requests and attempts < self.cfg.swap_requests * 30:
            attempts += 1
            if not pairs:
                break
            (team_id, shift_date), rows = self.rng.choice(pairs)
            first, second = self.rng.sample(rows, 2)
            if first["status"] not in {"SCHEDULED", "COMPLETED", "CONFIRMED"}:
                continue
            if second["status"] not in {"SCHEDULED", "COMPLETED", "CONFIRMED"}:
                continue
            if first["employee_id"] == second["employee_id"]:
                continue
            if first["shift_id"] == second["shift_id"]:
                continue
            status = self.rng.choices(statuses, weights=weights)[0]
            first_shift = self.shifts_by_id[first["shift_id"]]
            second_shift = self.shifts_by_id[second["shift_id"]]
            if status == "APPLIED" and shift_date < self.cfg.as_of_date:
                status = "APPROVED"
            if status == "APPLIED":
                first_skills = self.skills_by_employee[first["employee_id"]]
                second_skills = self.skills_by_employee[second["employee_id"]]
                required_first = set(self.skill_requirements[team_id][first_shift["shift_id"].rsplit("-", 1)[1]])
                required_second = set(self.skill_requirements[team_id][second_shift["shift_id"].rsplit("-", 1)[1]])
                if not required_first.issubset(second_skills) or not required_second.issubset(first_skills):
                    status = "REQUESTED"
                elif not rest_safe(second["employee_id"], first_shift, second["assignment_id"]):
                    status = "REQUESTED"
                elif not rest_safe(first["employee_id"], second_shift, first["assignment_id"]):
                    status = "REQUESTED"
            swap_id = f"SWP-{first_shift['shift_date'].year}-{self._next('swap'):06d}"
            target_agreed = status in {"APPROVED", "APPLIED"} or (
                status == "REQUESTED" and self.rng.random() < 0.35
            )
            created = first_shift["start_at"] - timedelta(days=6)
            self.data["swap_requests"].append(
                {
                    "swap_id": swap_id,
                    "requester_employee_id": first["employee_id"],
                    "target_employee_id": second["employee_id"],
                    "requester_assignment_id": first["assignment_id"],
                    "target_assignment_id": second["assignment_id"],
                    "reason": self.rng.choice(
                        ["Family commitment", "Medical appointment", "Personal errand",
                         "Exam preparation", "Travel plan"]
                    ),
                    "status": status,
                    "requester_agreed": True,
                    "target_agreed": target_agreed,
                    "target_responded_at": created + timedelta(hours=6) if target_agreed else None,
                    "manager_user_id": None,
                    "decided_at": created + timedelta(days=1)
                    if status in {"APPROVED", "APPLIED", "REJECTED"} else None,
                    "decision_comment": "Manager approved after coverage check"
                    if status in {"APPROVED", "APPLIED"} else (
                        "Rejected due to skill coverage" if status == "REJECTED" else None
                    ),
                    "applied_at": created + timedelta(days=1, hours=2)
                    if status == "APPLIED" else None,
                    "created_at": created,
                    "updated_at": created + timedelta(days=1),
                }
            )
            history_id += 1
            self.data["swap_approval_history"].append(
                {
                    "history_id": history_id,
                    "swap_id": swap_id,
                    "from_status": None,
                    "to_status": "REQUESTED",
                    "action": "REQUESTED",
                    "actor_user_id": None,
                    "comment": "Swap requested",
                    "created_at": created,
                }
            )
            if target_agreed:
                history_id += 1
                self.data["swap_approval_history"].append(
                    {
                        "history_id": history_id,
                        "swap_id": swap_id,
                        "from_status": "REQUESTED",
                        "to_status": "REQUESTED",
                        "action": "TARGET_ACCEPTED",
                        "actor_user_id": None,
                        "comment": "Target employee agreed",
                        "created_at": created + timedelta(hours=6),
                    }
                )
            if status in {"APPROVED", "APPLIED"}:
                history_id += 1
                self.data["swap_approval_history"].append(
                    {
                        "history_id": history_id,
                        "swap_id": swap_id,
                        "from_status": "REQUESTED",
                        "to_status": "APPROVED",
                        "action": "APPROVED",
                        "actor_user_id": None,
                        "comment": "Manager approval",
                        "created_at": created + timedelta(days=1),
                    }
                )
            elif status in {"REJECTED", "CANCELLED"}:
                history_id += 1
                self.data["swap_approval_history"].append(
                    {
                        "history_id": history_id,
                        "swap_id": swap_id,
                        "from_status": "REQUESTED",
                        "to_status": status,
                        "action": status,
                        "actor_user_id": None,
                        "comment": "Rejected by manager" if status == "REJECTED"
                        else "Withdrawn by requester",
                        "created_at": created + timedelta(days=1),
                    }
                )
            if status == "APPLIED":
                first["status"] = "SWAPPED_OUT"
                second["status"] = "SWAPPED_OUT"
                for original, new_employee in ((first, second["employee_id"]), (second, first["employee_id"])):
                    new_assignment = {
                        "assignment_id": f"ASG-{self._next('assignment'):06d}",
                        "shift_id": original["shift_id"],
                        "employee_id": new_employee,
                        "status": "SWAPPED_IN",
                        "assignment_source": "SWAP",
                        "assigned_at": created + timedelta(days=1, hours=2),
                        "scheduled_hours": 8.0,
                        "is_overtime": False,
                        "run_id": None,
                        "notes": f"Created by swap {swap_id}",
                        "created_at": created + timedelta(days=1, hours=2),
                        "updated_at": created + timedelta(days=1, hours=2),
                    }
                    self.data["shift_assignments"].append(new_assignment)
                    self.assignment_by_id[new_assignment["assignment_id"]] = new_assignment
                    assignments_by_employee[new_employee].append(new_assignment)
                history_id += 1
                self.data["swap_approval_history"].append(
                    {
                        "history_id": history_id,
                        "swap_id": swap_id,
                        "from_status": "APPROVED",
                        "to_status": "APPLIED",
                        "action": "APPLIED",
                        "actor_user_id": None,
                        "comment": "Swap applied to assignments",
                        "created_at": created + timedelta(days=1, hours=2),
                    }
                )

    # -------------------------------------------------------------- anomalies
    def _gt(self, scenario: str, issue_type: str, primary_type: str, primary_id: str,
            secondary_type: str, secondary_id: str, employee_id: str | None,
            shift_id: str | None, transaction_id: str | None, severity: str,
            expected_action: str, details: str) -> None:
        self.ground_truth.append(
            {
                "ground_truth_id": f"GT-{len(self.ground_truth) + 1:04d}",
                "scenario": scenario,
                "issue_type": issue_type,
                "primary_entity_type": primary_type,
                "primary_entity_id": primary_id,
                "secondary_entity_type": secondary_type,
                "secondary_entity_id": secondary_id,
                "employee_id": employee_id,
                "shift_id": shift_id,
                "transaction_id": transaction_id,
                "expected_detection": f"SchedulingException[{issue_type}]",
                "expected_action": expected_action,
                "severity": severity,
                "details": details,
            }
        )

    def inject_anomalies(self, per_type: int = 6) -> None:
        # Unapproved swaps first: they are transaction-only anomalies and must
        # not disturb later skill-deficit construction.
        self._inject_unapproved_swaps(per_type)
        self._inject_double_bookings(per_type)
        self._inject_leave_overlaps(per_type)
        self._inject_overtime(per_type)
        # Skill deficits are constructed last so no later step can re-qualify
        # the shift and accidentally erase the labelled scenario.
        self._inject_missing_skills(per_type)

    def _inject_double_bookings(self, count: int) -> None:
        active = [
            a for a in self.data["shift_assignments"]
            if a["status"] in ACTIVE_STATUSES
        ]
        self.rng.shuffle(active)
        used = set()
        for assignment in active:
            if len([g for g in self.ground_truth if g["scenario"] == "double_booking"]) >= count:
                break
            if assignment["employee_id"] in used:
                continue
            shift = self.shifts_by_id[assignment["shift_id"]]
            code = shift["shift_id"].rsplit("-", 1)[1]
            other = next(
                (
                    s for s in self.data["shifts"]
                    if s["shift_date"] == shift["shift_date"]
                    and s["shift_id"].endswith(f"-{code}")
                    and s["team_id"] != shift["team_id"]
                ),
                None,
            )
            if other is None:
                continue
            if any(
                a["shift_id"] == other["shift_id"] and a["employee_id"] == assignment["employee_id"]
                for a in self.data["shift_assignments"]
            ):
                continue
            new_id = f"ASG-{self._next('assignment'):06d}"
            self.data["shift_assignments"].append(
                {
                    "assignment_id": new_id,
                    "shift_id": other["shift_id"],
                    "employee_id": assignment["employee_id"],
                    "status": "SCHEDULED",
                    "assignment_source": "MANUAL",
                    "assigned_at": datetime(2026, 10, 15, 9, 0),
                    "scheduled_hours": 8.0,
                    "is_overtime": False,
                    "run_id": None,
                    "notes": "Deliberate double-booking anomaly for detection testing.",
                    "created_at": datetime(2026, 10, 15, 9, 0),
                    "updated_at": datetime(2026, 10, 15, 9, 0),
                }
            )
            used.add(assignment["employee_id"])
            self._gt(
                "double_booking", "DOUBLE_BOOKING", "Employee", assignment["employee_id"],
                "Shift", other["shift_id"], assignment["employee_id"], other["shift_id"], None,
                "CRITICAL", "Remove one overlapping assignment and notify the manager",
                f"Employee also assigned to {assignment['shift_id']} at the same time.",
            )

    def _inject_leave_overlaps(self, count: int) -> None:
        approved = [l for l in self.data["leave_requests"] if l["status"] == "APPROVED"]
        self.rng.shuffle(approved)
        existing_by_employee: dict[str, list[dict]] = defaultdict(list)
        for assignment in self.data["shift_assignments"]:
            if assignment["status"] in ACTIVE_STATUSES:
                existing_by_employee[assignment["employee_id"]].append(assignment)

        def rest_safe(employee_id: str, shift: dict) -> bool:
            for other in existing_by_employee.get(employee_id, []):
                other_shift = self.shifts_by_id[other["shift_id"]]
                if other_shift["shift_date"] == shift["shift_date"]:
                    return False
                if other_shift["end_at"] <= shift["start_at"]:
                    gap = (shift["start_at"] - other_shift["end_at"]).total_seconds() / 3600
                else:
                    gap = (other_shift["start_at"] - shift["end_at"]).total_seconds() / 3600
                if gap < 11:
                    return False
            return True

        created = 0
        for leave in approved:
            if created >= count:
                break
            employee_id = leave["employee_id"]
            team_id = self.employee_by_id[employee_id]["team_id"]
            day = leave["start_date"]
            found = None
            while day <= leave["end_date"]:
                candidates = [
                    s for s in self.data["shifts"]
                    if s["team_id"] == team_id and s["shift_date"] == day
                ]
                for shift in candidates:
                    if any(
                        a["shift_id"] == shift["shift_id"] and a["employee_id"] == employee_id
                        for a in self.data["shift_assignments"]
                    ):
                        continue
                    if rest_safe(employee_id, shift):
                        found = shift
                        break
                if found:
                    break
                day += timedelta(days=1)
            if not found:
                continue
            new_id = f"ASG-{self._next('assignment'):06d}"
            self.data["shift_assignments"].append(
                {
                    "assignment_id": new_id,
                    "shift_id": found["shift_id"],
                    "employee_id": employee_id,
                    "status": "SCHEDULED",
                    "assignment_source": "MANUAL",
                    "assigned_at": datetime(2026, 10, 10, 9, 0),
                    "scheduled_hours": 8.0,
                    "is_overtime": False,
                    "run_id": None,
                    "notes": "Deliberate leave-overlap anomaly for detection testing.",
                    "created_at": datetime(2026, 10, 10, 9, 0),
                    "updated_at": datetime(2026, 10, 10, 9, 0),
                }
            )
            created += 1
            self._gt(
                "leave_overlap", "LEAVE_OVERLAP", "Employee", employee_id,
                "Shift", found["shift_id"], employee_id, found["shift_id"],
                leave["leave_id"], "HIGH", "Reassign the shift; approved leave takes priority",
                f"Approved leave {leave['leave_id']} covers {found['shift_date']}.",
            )

    def _inject_missing_skills(self, count: int) -> None:
        active_assignments = [
            a for a in self.data["shift_assignments"] if a["status"] in ACTIVE_STATUSES
        ]
        by_shift: dict[str, list[dict]] = defaultdict(list)
        by_employee: dict[str, list[dict]] = defaultdict(list)
        on_date_employees: dict[date, set[str]] = defaultdict(set)
        for assignment in active_assignments:
            by_shift[assignment["shift_id"]].append(assignment)
            by_employee[assignment["employee_id"]].append(assignment)
            on_date_employees[self.shifts_by_id[assignment["shift_id"]]["shift_date"]].add(
                assignment["employee_id"]
            )

        def can_take(employee_id: str, shift: dict) -> bool:
            if employee_id in on_date_employees.get(shift["shift_date"], set()):
                return False
            if self.employee_by_id[employee_id]["status"] != "ACTIVE":
                return False
            if shift["shift_date"] in self.approved_leave_dates[employee_id]:
                return False
            if not self.availability[employee_id].get(shift["shift_date"].weekday(), True):
                return False
            for other in by_employee.get(employee_id, []):
                other_shift = self.shifts_by_id[other["shift_id"]]
                if other_shift["start_at"] < shift["end_at"] and shift["start_at"] < other_shift["end_at"]:
                    return False
                if other_shift["end_at"] <= shift["start_at"]:
                    gap = (shift["start_at"] - other_shift["end_at"]).total_seconds() / 3600
                else:
                    gap = (other_shift["start_at"] - shift["end_at"]).total_seconds() / 3600
                if gap < 11:
                    return False
            return True

        created = 0
        shifts = list(self.data["shifts"])
        self.rng.shuffle(shifts)
        for shift in shifts:
            if created >= count:
                break
            team_id = shift["team_id"]
            code = shift["shift_id"].rsplit("-", 1)[1]
            assignments = [
                a for a in by_shift.get(shift["shift_id"], [])
                if a["status"] in ACTIVE_STATUSES
            ]
            if len(assignments) < 1:
                continue
            assigned_employees = {a["employee_id"] for a in assignments}
            options = []
            for skill_id in self.skill_requirements[team_id][code]:
                qualified = [
                    a for a in assignments
                    if skill_id in self.skills_by_employee[a["employee_id"]]
                ]
                if not qualified:
                    continue
                pool = [
                    e for e in self.team_employees[team_id]
                    if e not in assigned_employees
                    and skill_id not in self.skills_by_employee[e]
                    and can_take(e, shift)
                ]
                if len(pool) < len(qualified):
                    pool += [
                        e["employee_id"]
                        for e in self.data["employees"]
                        if e["team_id"] != team_id
                        and e["employee_id"] not in assigned_employees
                        and skill_id not in self.skills_by_employee[e["employee_id"]]
                        and can_take(e["employee_id"], shift)
                    ][: len(qualified) - len(pool)]
                if len(pool) >= len(qualified):
                    options.append((len(qualified), skill_id, qualified, pool))
            if not options:
                continue
            options.sort(key=lambda item: item[0])
            _, chosen_skill, qualified, pool = options[0]
            replacements = pool[: len(qualified)]
            for victim in qualified:
                victim["status"] = "SWAPPED_OUT"
            for replacement in replacements:
                new_id = f"ASG-{self._next('assignment'):06d}"
                new_assignment = {
                    "assignment_id": new_id,
                    "shift_id": shift["shift_id"],
                    "employee_id": replacement,
                    "status": "SCHEDULED",
                    "assignment_source": "MANUAL",
                    "assigned_at": datetime(2026, 10, 12, 9, 0),
                    "scheduled_hours": 8.0,
                    "is_overtime": False,
                    "run_id": None,
                    "notes": "Deliberate missing-skill anomaly for detection testing.",
                    "created_at": datetime(2026, 10, 12, 9, 0),
                    "updated_at": datetime(2026, 10, 12, 9, 0),
                }
                self.data["shift_assignments"].append(new_assignment)
                by_shift[shift["shift_id"]].append(new_assignment)
                by_employee[replacement].append(new_assignment)
                on_date_employees[shift["shift_date"]].add(replacement)
            created += 1
            # Replacing multi-skilled staff can remove qualification for more
            # than one requirement; label every resulting deficit.
            current_assignments = [
                a for a in by_shift.get(shift["shift_id"], [])
                if a["status"] in ACTIVE_STATUSES
            ]
            for skill_id in self.skill_requirements[team_id][code]:
                qualified_now = sum(
                    1 for a in current_assignments
                    if skill_id in self.skills_by_employee[a["employee_id"]]
                )
                minimum = 1
                if qualified_now < minimum:
                    self._gt(
                        "missing_skill", "MISSING_SKILL", "Shift", shift["shift_id"],
                        "Skill", skill_id, replacements[0], shift["shift_id"], skill_id,
                        "HIGH", "Assign a qualified employee or arrange training coverage",
                        f"Required skill {skill_id} has {qualified_now} qualified assignee(s) "
                        f"(minimum {minimum}) after the manual replacement.",
                    )

    def _inject_overtime(self, count: int) -> None:
        events = [
            e for e in self.data["attendance_events"]
            if e["actual_check_in"] is not None and e["actual_check_out"] is not None
        ]
        self.rng.shuffle(events)
        used = set()
        created = 0
        for event in events:
            if created >= count:
                break
            if event["employee_id"] in used:
                continue
            employee = self.employee_by_id[event["employee_id"]]
            week = event["scheduled_start"].date() - timedelta(
                days=event["scheduled_start"].weekday()
            )
            week_events = [
                e for e in self.data["attendance_events"]
                if e["employee_id"] == event["employee_id"]
                and week <= e["scheduled_start"].date() <= week + timedelta(days=6)
            ]
            actual = sum(e["actual_hours"] for e in week_events)
            target = 40 + float(employee["overtime_cap_weekly"]) + 4
            extra = max(1.0, target - actual)
            event["actual_check_out"] = event["actual_check_out"] + timedelta(hours=extra)
            event["actual_hours"] = round(
                (event["actual_check_out"] - event["actual_check_in"]).total_seconds() / 3600, 2
            )
            event["overtime_hours"] = round(max(0.0, event["actual_hours"] - 8.0), 2)
            event["status"] = "PRESENT"
            event["notes"] = "Deliberate overtime-cap anomaly for detection testing."
            used.add(event["employee_id"])
            created += 1
            week_start = week
            self._gt(
                "overtime_cap", "OVERTIME_CAP", "Employee", event["employee_id"],
                "Week", week_start.isoformat(), event["employee_id"], None,
                week_start.isoformat(), "MEDIUM", "Rebalance the roster to stay within overtime cap",
                f"Weekly actual hours exceed the 40h standard by more than the "
                f"{employee['overtime_cap_weekly']:.0f}h overtime cap.",
            )

    def _inject_unapproved_swaps(self, count: int) -> None:
        future = [
            a for a in self.data["shift_assignments"]
            if a["status"] in {"SCHEDULED", "CONFIRMED"}
            and self.shifts_by_id[a["shift_id"]]["shift_date"] >= self.cfg.as_of_date
        ]
        self.rng.shuffle(future)
        created = 0
        used = set()
        for assignment in future:
            if created >= count:
                break
            if assignment["assignment_id"] in used:
                continue
            shift = self.shifts_by_id[assignment["shift_id"]]
            team_id = shift["team_id"]
            partner = next(
                (
                    a for a in future
                    if a["status"] in {"SCHEDULED", "CONFIRMED"}
                    and a["employee_id"] != assignment["employee_id"]
                    and a["shift_id"] != assignment["shift_id"]
                    and self.shifts_by_id[a["shift_id"]]["team_id"] == team_id
                    and self.shifts_by_id[a["shift_id"]]["shift_date"] == shift["shift_date"]
                    and a["assignment_id"] not in used
                ),
                None,
            )
            if partner is None:
                continue
            swap_id = f"SWP-{shift['shift_date'].year}-{self._next('swap'):06d}"
            created_at = datetime(2026, 11, 13, 9, 0)
            self.data["swap_requests"].append(
                {
                    "swap_id": swap_id,
                    "requester_employee_id": assignment["employee_id"],
                    "target_employee_id": partner["employee_id"],
                    "requester_assignment_id": assignment["assignment_id"],
                    "target_assignment_id": partner["assignment_id"],
                    "reason": "Deliberate unapproved swap anomaly for detection testing.",
                    "status": "APPLIED",
                    "requester_agreed": True,
                    "target_agreed": True,
                    "target_responded_at": created_at,
                    "manager_user_id": None,
                    "decided_at": None,
                    "decision_comment": None,
                    "applied_at": created_at,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )
            # Transaction-state anomaly only: the roster itself is left intact,
            # so the detector tests the missing approval event rather than a
            # side-effect such as a new double booking or skill gap.
            used.add(assignment["assignment_id"])
            used.add(partner["assignment_id"])
            created += 1
            self._gt(
                "unapproved_swap", "UNAPPROVED_SWAP", "SwapRequest", swap_id,
                "None", "", assignment["employee_id"], assignment["shift_id"], swap_id,
                "CRITICAL", "Freeze the swap, notify the manager and restore the original roster",
                "Swap status is APPLIED but no manager approval event exists.",
            )

    # ------------------------------------------------------------------ write
    def _records_for_csv(self, table_name: str) -> list[dict]:
        return [
            {
                key: (value.value if hasattr(value, "value") else value)
                for key, value in row.items()
            }
            for row in self.data[table_name]
        ]

    def write_csvs(self) -> dict[str, Path]:
        csv_dir = self.cfg.output_dir / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        files = {}
        for table_name in TABLE_ORDER:
            rows = self._records_for_csv(table_name)
            if not rows:
                continue
            columns = list(Base.metadata.tables[table_name].columns.keys())
            frame = pd.DataFrame(rows)
            for column in columns:
                if column not in frame.columns:
                    frame[column] = None
            frame = frame[columns]
            path = csv_dir / f"{table_name}.csv"
            frame.to_csv(path, index=False)
            files[table_name] = path
        return files

    def write_json(self) -> dict[str, Path]:
        json_dir = self.cfg.output_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        files = {}
        for table_name in sorted(MASTER_TABLES):
            rows = self._records_for_csv(table_name)
            path = json_dir / f"{table_name}.json"
            path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
            files[table_name] = path
        return files

    def write_ground_truth(self) -> dict[str, Path]:
        directory = self.cfg.output_dir / "ground_truth"
        directory.mkdir(parents=True, exist_ok=True)
        truth_dir = PROJECT_ROOT / "ground_truth"
        truth_dir.mkdir(parents=True, exist_ok=True)
        csv_path = directory / "ground_truth.csv"
        json_path = directory / "ground_truth.json"
        pd.DataFrame(self.ground_truth).to_csv(csv_path, index=False)
        payload = {
            "dataset": self.cfg.scale,
            "seed": self.cfg.seed,
            "as_of_date": self.cfg.as_of_date.isoformat(),
            "scenario_count": len(self.ground_truth),
            "methodology": (
                "Anomalies were injected after valid baseline generation. Labels live only in "
                "this file and are never loaded into the operational database or used as "
                "detection features."
            ),
            "scenarios": self.ground_truth,
        }
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        # Canonical copies at project root for evaluators.
        pd.DataFrame(self.ground_truth).to_csv(truth_dir / "ground_truth.csv", index=False)
        (truth_dir / "ground_truth.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        return {"csv": csv_path, "json": json_path}

    def write_manifest(self, files: dict[str, Path], validation: dict) -> dict:
        checksums = {}
        for table_name, path in files.items():
            checksums[path.name] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": len(self.data[table_name]),
                "bytes": path.stat().st_size,
            }
        payload = {
            "generator": "WorkSync AI synthetic data generator",
            "generator_version": "1.0.0",
            "seed": self.cfg.seed,
            "scale": self.cfg.scale,
            "as_of_date": self.cfg.as_of_date.isoformat(),
            "start_date": self.cfg.start_date.isoformat(),
            "end_date": self.cfg.end_date.isoformat(),
            "config": {
                "teams": self.cfg.teams,
                "employees": self.cfg.employees,
                "days": self.cfg.days,
                "leave_requests": self.cfg.leave_requests,
                "swap_requests": self.cfg.swap_requests,
            },
            "row_counts": {name: len(rows) for name, rows in self.data.items()},
            "checksums": checksums,
            "unfilled_baseline_shifts": len(self.unfilled_shifts),
            "validation": validation,
            "provenance": "Fully synthetic; no external or confidential data used.",
        }
        path = self.cfg.output_dir / "manifest.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def write_sql(self) -> Path:
        """Portable PostgreSQL schema plus master-data inserts for seeding."""
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.schema import CreateIndex, CreateTable

        database_dir = PROJECT_ROOT / "database"
        database_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "-- WorkSync AI PostgreSQL schema",
            "-- Generated from the SQLAlchemy metadata; use Alembic for upgrades.",
            "",
        ]
        for table in Base.metadata.sorted_tables:
            lines.append(str(CreateTable(table).compile(dialect=postgresql.dialect())).strip() + ";")
            for index in table.indexes:
                lines.append(str(CreateIndex(index).compile(dialect=postgresql.dialect())).strip() + ";")
            lines.append("")
        (database_dir / "schema.sql").write_text("\n".join(lines), encoding="utf-8")

        # Master-data SQL seed (events are loaded from CSV for performance).
        def literal(value):
            if value is None:
                return "NULL"
            if isinstance(value, bool):
                return "TRUE" if value else "FALSE"
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, datetime):
                return "'" + value.isoformat(sep=" ") + "'"
            if isinstance(value, (date, time)):
                return "'" + value.isoformat() + "'"
            return "'" + str(value).replace("'", "''") + "'"

        insert_lines = ["-- WorkSync AI master-data seed", "BEGIN;", ""]
        for table_name in TABLE_ORDER:
            if table_name not in MASTER_TABLES:
                continue
            rows = self._records_for_csv(table_name)
            if not rows:
                continue
            table = Base.metadata.tables[table_name]
            columns = [c.name for c in table.columns if c.name in rows[0]]
            for row in rows:
                values = ", ".join(literal(row.get(column)) for column in columns)
                insert_lines.append(
                    f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({values}) "
                    "ON CONFLICT DO NOTHING;"
                )
        insert_lines.append("COMMIT;")
        path = database_dir / "seed_master.sql"
        path.write_text("\n".join(insert_lines), encoding="utf-8")
        return path

    def write_database(self) -> None:
        if not self.cfg.write_db:
            return
        url = self.cfg.database_url
        if not url:
            url = f"sqlite:///{(PROJECT_ROOT / 'backend' / 'worksync.db').as_posix()}"
        if url.startswith("sqlite:///"):
            path = Path(url.replace("sqlite:///", ""))
            if path.exists():
                path.unlink()
            for suffix in ("-wal", "-shm"):
                sidecar = Path(str(path) + suffix)
                if sidecar.exists():
                    sidecar.unlink()
        engine = create_engine(url, future=True)
        if url.startswith("sqlite"):
            @event.listens_for(engine, "connect")
            def _fk(dbapi_connection, _record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            for table_name in TABLE_ORDER:
                rows = self.data[table_name]
                if not rows:
                    continue
                table = Base.metadata.tables[table_name]
                columns = set(table.columns.keys())
                clean = [{k: v for k, v in row.items() if k in columns} for row in rows]
                for start in range(0, len(clean), 2000):
                    connection.execute(table.insert(), clean[start:start + 2000])
        engine.dispose()

    def run(self) -> dict:
        self.generate_skills()
        self.generate_teams()
        self.generate_employees()
        self.generate_employee_skills()
        self.generate_team_managers()
        self.generate_shift_templates()
        self.generate_coverage()
        self.generate_holidays()
        self.generate_leave_policies()
        self.generate_availability()
        self.generate_leaves()
        self.generate_shifts()
        self.generate_assignments()
        self.generate_attendance()
        self.generate_swaps()

        from data_generation.validators import validate_dataset

        baseline_validation = validate_dataset(self.data, mode="baseline",
                                               ground_truth=self.ground_truth)
        self.inject_anomalies()

        from data_generation.validators import validate_anomalies

        anomaly_validation = validate_anomalies(self.data, self.ground_truth)
        validation = {
            "baseline": baseline_validation,
            "anomalies": anomaly_validation,
            "status": "PASS" if baseline_validation["failures"] == 0
            and anomaly_validation["missing"] == 0 else "FAIL",
        }
        files = self.write_csvs()
        self.write_json()
        self.write_ground_truth()
        self.write_sql()
        manifest = self.write_manifest(files, validation)
        self.write_database()
        summary_path = self.cfg.output_dir / "validation_summary.json"
        summary_path.write_text(json.dumps(validation, indent=2), encoding="utf-8")
        return {
            "manifest": manifest,
            "validation": validation,
            "ground_truth": self.ground_truth,
            "unfilled_shifts": self.unfilled_shifts[:20],
        }
