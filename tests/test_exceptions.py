from __future__ import annotations

from datetime import date, datetime

from app.models.attendance import AttendanceEvent
from app.models.leave import LeaveRequest
from app.models.master import Shift
from app.models.scheduling import ShiftAssignment, SwapRequest


def _seed_anomalies(session_factory):
    with session_factory() as db:
        db.add_all([
            Shift(shift_id="SHIFT-2027-01-08-001-A", shift_date=date(2027, 1, 8),
                  shift_template_id="TPL-001", team_id="TEAM-001",
                  start_at=datetime(2027, 1, 8, 6), end_at=datetime(2027, 1, 8, 14),
                  required_staff=1, status="PUBLISHED"),
            Shift(shift_id="SHIFT-2027-01-08-002-A", shift_date=date(2027, 1, 8),
                  shift_template_id="TPL-001", team_id="TEAM-002",
                  start_at=datetime(2027, 1, 8, 6), end_at=datetime(2027, 1, 8, 14),
                  required_staff=1, status="PUBLISHED"),
            Shift(shift_id="SHIFT-2027-01-09-001-A", shift_date=date(2027, 1, 9),
                  shift_template_id="TPL-001", team_id="TEAM-001",
                  start_at=datetime(2027, 1, 9, 6), end_at=datetime(2027, 1, 9, 14),
                  required_staff=1, status="PUBLISHED"),
            Shift(shift_id="SHIFT-2027-01-10-002-A", shift_date=date(2027, 1, 10),
                  shift_template_id="TPL-001", team_id="TEAM-002",
                  start_at=datetime(2027, 1, 10, 6), end_at=datetime(2027, 1, 10, 14),
                  required_staff=1, status="PUBLISHED"),
            Shift(shift_id="SHIFT-2026-11-11-002-A", shift_date=date(2026, 11, 11),
                  shift_template_id="TPL-001", team_id="TEAM-002",
                  start_at=datetime(2026, 11, 11, 6), end_at=datetime(2026, 11, 11, 14),
                  required_staff=1, status="COMPLETED"),
        ])
        db.flush()
        db.add_all([
            ShiftAssignment(assignment_id="ASG-900001", shift_id="SHIFT-2027-01-08-001-A",
                            employee_id="EMP-000005", status="SCHEDULED",
                            assignment_source="MANUAL", scheduled_hours=8),
            ShiftAssignment(assignment_id="ASG-900002", shift_id="SHIFT-2027-01-08-002-A",
                            employee_id="EMP-000005", status="SCHEDULED",
                            assignment_source="MANUAL", scheduled_hours=8),
            ShiftAssignment(assignment_id="ASG-900003", shift_id="SHIFT-2027-01-09-001-A",
                            employee_id="EMP-000006", status="SCHEDULED",
                            assignment_source="MANUAL", scheduled_hours=8),
            ShiftAssignment(assignment_id="ASG-900004", shift_id="SHIFT-2027-01-10-002-A",
                            employee_id="EMP-000007", status="SCHEDULED",
                            assignment_source="MANUAL", scheduled_hours=8),
            ShiftAssignment(assignment_id="ASG-900005", shift_id="SHIFT-2026-11-11-002-A",
                            employee_id="EMP-000008", status="COMPLETED",
                            assignment_source="BASELINE", scheduled_hours=8),
        ])
        db.add(
            LeaveRequest(
                leave_id="LVE-2027-900001",
                employee_id="EMP-000006",
                policy_id="POL-001",
                leave_type="ANNUAL",
                start_date=date(2027, 1, 9),
                end_date=date(2027, 1, 9),
                total_days=1,
                reason="Seeded overlap",
                status="APPROVED",
            )
        )
        db.add(
            AttendanceEvent(
                attendance_id="ATT-EMP-000008-20261111T060000",
                employee_id="EMP-000008",
                shift_id="SHIFT-2026-11-11-002-A",
                assignment_id="ASG-900005",
                scheduled_start=datetime(2026, 11, 11, 6),
                scheduled_end=datetime(2026, 11, 11, 14),
                actual_check_in=datetime(2026, 11, 11, 6),
                actual_check_out=datetime(2026, 11, 13, 12),
                status="PRESENT",
                actual_hours=54.0,
                overtime_hours=46.0,
                source="MANUAL",
                reconciliation_status="MATCHED",
            )
        )
        db.add(
            SwapRequest(
                swap_id="SWP-2027-900001",
                requester_employee_id="EMP-000002",
                target_employee_id="EMP-000004",
                requester_assignment_id="ASG-000002",
                target_assignment_id="ASG-000003",
                reason="Applied without approval",
                status="APPLIED",
                requester_agreed=True,
                target_agreed=True,
            )
        )
        db.commit()


def test_detector_finds_all_required_anomaly_types(client, admin_headers, app_env):
    _seed_anomalies(app_env["session"])
    response = client.post("/api/exceptions/detect", headers=admin_headers)
    assert response.status_code == 200, response.text
    by_type = response.json()["by_type"]
    for issue_type in (
        "DOUBLE_BOOKING",
        "LEAVE_OVERLAP",
        "MISSING_SKILL",
        "OVERTIME_CAP",
        "UNAPPROVED_SWAP",
    ):
        assert by_type.get(issue_type, 0) >= 1, f"{issue_type} was not detected: {by_type}"

    listed = client.get("/api/exceptions?issue_type=DOUBLE_BOOKING", headers=admin_headers)
    assert listed.status_code == 200
    issue = listed.json()["items"][0]
    resolved = client.put(
        f"/api/exceptions/{issue['issue_id']}/resolve",
        headers=admin_headers,
        json={"resolution_status": "RESOLVED", "note": "Reassigned one shift"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolution_status"] == "RESOLVED"


def test_employee_only_sees_own_exceptions(client, employee_headers, admin_headers, app_env):
    _seed_anomalies(app_env["session"])
    client.post("/api/exceptions/detect", headers=admin_headers)
    response = client.get("/api/exceptions?page_size=200", headers=employee_headers)
    assert response.status_code == 200
    assert all(item["employee_id"] == "EMP-000002" for item in response.json()["items"])
