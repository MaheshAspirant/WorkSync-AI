from __future__ import annotations


def _leave_payload(start="2027-01-11", end="2027-01-12", leave_type="ANNUAL"):
    return {
        "leave_type": leave_type,
        "start_date": start,
        "end_date": end,
        "reason": "Test leave request",
    }


def test_leave_submit_and_approve(client, employee_headers, manager_headers):
    created = client.post("/api/leaves", headers=employee_headers, json=_leave_payload())
    assert created.status_code == 201, created.text
    leave = created.json()
    assert leave["status"] == "PENDING"
    assert leave["total_days"] == 2
    assert len(leave["history"]) >= 1

    approved = client.put(
        f"/api/leaves/{leave['leave_id']}/approve",
        headers=manager_headers,
        json={"comment": "Coverage confirmed"},
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "APPROVED"
    assert body["decided_by_user_id"]
    assert any(event["to_status"] == "APPROVED" for event in body["history"])


def test_overlapping_leave_is_rejected(client, employee_headers):
    first = client.post("/api/leaves", headers=employee_headers, json=_leave_payload("2027-02-01", "2027-02-03"))
    assert first.status_code == 201
    overlap = client.post("/api/leaves", headers=employee_headers, json=_leave_payload("2027-02-02", "2027-02-04"))
    assert overlap.status_code == 409


def test_rejection_requires_comment(client, employee_headers, manager_headers):
    leave = client.post("/api/leaves", headers=employee_headers, json=_leave_payload("2027-02-08", "2027-02-09")).json()
    no_comment = client.put(f"/api/leaves/{leave['leave_id']}/reject", headers=manager_headers, json={})
    assert no_comment.status_code == 422
    rejected = client.put(
        f"/api/leaves/{leave['leave_id']}/reject",
        headers=manager_headers,
        json={"comment": "Insufficient coverage"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"


def test_employee_can_cancel_pending_leave(client, employee_headers):
    leave = client.post("/api/leaves", headers=employee_headers, json=_leave_payload("2027-02-15", "2027-02-16")).json()
    cancelled = client.put(f"/api/leaves/{leave['leave_id']}/cancel", headers=employee_headers, json={})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


def test_manager_cannot_approve_own_leave(client, manager_headers):
    leave = client.post("/api/leaves", headers=manager_headers, json=_leave_payload("2027-02-22", "2027-02-23")).json()
    response = client.put(f"/api/leaves/{leave['leave_id']}/approve", headers=manager_headers, json={})
    assert response.status_code == 403


def test_leave_balance_endpoint(client, employee_headers):
    response = client.get("/api/leaves/balance/EMP-000002?year=2027", headers=employee_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["employee_id"] == "EMP-000002"
    assert {row["leave_type"] for row in payload["balances"]} >= {"ANNUAL", "SICK"}
