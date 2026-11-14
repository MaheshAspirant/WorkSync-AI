from __future__ import annotations


def test_attendance_derives_hours_and_overtime(client, employee_headers, manager_headers):
    created = client.post(
        "/api/attendance",
        headers=employee_headers,
        json={
            "assignment_id": "ASG-000001",
            "check_in": "2026-11-10T06:20:00",
            "check_out": "2026-11-10T18:00:00",
            "source": "MANUAL",
            "notes": "Recorded in test",
        },
    )
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["status"] == "LATE"
    assert event["late_minutes"] == 20
    assert event["actual_hours"] == 11.67
    assert event["overtime_hours"] == 3.67
    assert event["reconciliation_status"] == "MATCHED"

    duplicate = client.post(
        "/api/attendance",
        headers=employee_headers,
        json={"assignment_id": "ASG-000001", "check_in": "2026-11-10T06:00:00"},
    )
    assert duplicate.status_code == 409

    updated = client.put(
        f"/api/attendance/{event['attendance_id']}",
        headers=manager_headers,
        json={"check_in": "2026-11-10T06:00:00", "check_out": "2026-11-10T18:30:00", "notes": "Corrected"},
    )
    assert updated.status_code == 200
    assert updated.json()["actual_hours"] == 12.5
    assert updated.json()["overtime_hours"] == 4.5


def test_attendance_summary_and_overtime_endpoints(client, employee_headers):
    client.post(
        "/api/attendance",
        headers=employee_headers,
        json={
            "assignment_id": "ASG-000001",
            "check_in": "2026-11-10T06:00:00",
            "check_out": "2026-11-10T17:00:00",
        },
    )
    summary = client.get(
        "/api/attendance/summary/EMP-000002?start=2026-11-01&end=2026-11-30",
        headers=employee_headers,
    )
    assert summary.status_code == 200
    body = summary.json()
    assert body["scheduled_shifts"] == 1
    assert body["total_actual_hours"] == 11.0
    assert body["absence_rate"] == 0.0

    overtime = client.get(
        "/api/attendance/overtime?start=2026-11-01&end=2026-11-30",
        headers=employee_headers,
    )
    assert overtime.status_code == 200
    assert len(overtime.json()["rows"]) == 1
    assert overtime.json()["rows"][0]["actual_hours"] == 11.0
