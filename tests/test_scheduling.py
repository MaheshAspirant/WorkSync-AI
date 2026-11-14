from __future__ import annotations

from datetime import date, datetime

from app.models.master import Shift


def _approve_leave(client, employee_headers, manager_headers, start, end):
    created = client.post(
        "/api/leaves",
        headers=employee_headers,
        json={"leave_type": "ANNUAL", "start_date": start, "end_date": end, "reason": "Scheduling test leave"},
    )
    assert created.status_code == 201, created.text
    approved = client.put(
        f"/api/leaves/{created.json()['leave_id']}/approve",
        headers=manager_headers,
        json={"comment": "Approved for test"},
    )
    assert approved.status_code == 200, approved.text


def test_scheduler_respects_approved_leave_and_explains(client, admin_headers, employee_headers, manager_headers):
    _approve_leave(client, employee_headers, manager_headers, "2027-01-05", "2027-01-06")

    response = client.post(
        "/api/scheduling/generate",
        headers=admin_headers,
        json={
            "team_id": "TEAM-001",
            "start_date": "2027-01-05",
            "end_date": "2027-01-06",
            "replace_existing": True,
            "time_limit_seconds": 5,
        },
    )
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] in {"COMPLETED", "PARTIAL"}
    assert run["hard_violations"] == 0
    assert run["decisions"], "Every generated assignment must have an explanation"

    assignments = client.get(
        "/api/scheduling/assignments?team_id=TEAM-001&start=2027-01-05&end=2027-01-06&page_size=100",
        headers=admin_headers,
    ).json()["items"]
    active_statuses = {"SCHEDULED", "CONFIRMED", "COMPLETED", "SWAPPED_IN"}
    leave_assignments = [
        a for a in assignments
        if a["employee_id"] == "EMP-000002" and a["status"] in active_statuses
    ]
    assert leave_assignments == []

    decision = run["decisions"][0]
    assert decision["reason"]
    assert decision["constraint_evaluation"]["leave_eligible"] is True
    assert "Skill match" in decision["reason"]


def test_infeasible_scope_returns_explicit_gaps(client, admin_headers, app_env):
    with app_env["session"]() as db:
        db.add(
            Shift(
                shift_id="SHIFT-2027-01-07-002-A",
                shift_date=date(2027, 1, 7),
                shift_template_id="TPL-001",
                team_id="TEAM-002",
                start_at=datetime(2027, 1, 7, 6, 0),
                end_at=datetime(2027, 1, 7, 14, 0),
                required_staff=4,
                status="PUBLISHED",
            )
        )
        db.commit()

    response = client.post(
        "/api/scheduling/generate",
        headers=admin_headers,
        json={
            "team_id": "TEAM-002",
            "start_date": "2027-01-07",
            "end_date": "2027-01-07",
            "replace_existing": True,
            "time_limit_seconds": 3,
        },
    )
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] in {"PARTIAL", "INFEASIBLE"}
    assert run["coverage_gaps"] > 0
    assert run["message"]


def test_schedule_run_and_decisions_are_queryable(client, admin_headers):
    generated = client.post(
        "/api/scheduling/generate",
        headers=admin_headers,
        json={
            "team_id": "TEAM-001",
            "start_date": "2027-01-05",
            "end_date": "2027-01-05",
            "replace_existing": False,
            "time_limit_seconds": 3,
        },
    )
    assert generated.status_code == 201
    run_id = generated.json()["run_id"]
    runs = client.get("/api/scheduling/runs", headers=admin_headers)
    assert runs.status_code == 200
    assert any(row["run_id"] == run_id for row in runs.json()["items"])
    detail = client.get(f"/api/scheduling/runs/{run_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run_id
