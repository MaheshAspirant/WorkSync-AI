from __future__ import annotations

from datetime import date, datetime

from app.models.scheduling import ShiftAssignment, SwapRequest


def test_swap_requires_target_agreement_then_manager_approval(client, employee_headers, target_headers, manager_headers, app_env):
    created = client.post(
        "/api/swaps",
        headers=employee_headers,
        json={
            "requester_assignment_id": "ASG-000002",
            "target_assignment_id": "ASG-000003",
            "reason": "Family commitment",
        },
    )
    assert created.status_code == 201, created.text
    swap = created.json()
    assert swap["status"] == "REQUESTED"

    # Manager cannot approve before the target agrees.
    premature = client.put(
        f"/api/swaps/{swap['swap_id']}/approve",
        headers=manager_headers,
        json={"comment": "Too early"},
    )
    assert premature.status_code == 409

    agreed = client.put(
        f"/api/swaps/{swap['swap_id']}/target-response",
        headers=target_headers,
        json={"agree": True, "comment": "Happy to swap"},
    )
    assert agreed.status_code == 200
    assert agreed.json()["target_agreed"] is True

    approved = client.put(
        f"/api/swaps/{swap['swap_id']}/approve",
        headers=manager_headers,
        json={"comment": "Coverage and skills verified"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPLIED"
    assert any(event["to_status"] == "APPLIED" for event in approved.json()["history"])

    with app_env["session"]() as db:
        old_a = db.get(ShiftAssignment, "ASG-000002")
        old_b = db.get(ShiftAssignment, "ASG-000003")
        assert old_a.status.value == "SWAPPED_OUT"
        assert old_b.status.value == "SWAPPED_OUT"
        new_rows = db.query(ShiftAssignment).filter(
            ShiftAssignment.assignment_source == "SWAP",
            ShiftAssignment.status == "SWAPPED_IN",
        ).all()
        assert len(new_rows) == 2


def test_unapproved_swap_cannot_be_applied(client, manager_headers, app_env):
    with app_env["session"]() as db:
        db.add(
            SwapRequest(
                swap_id="SWP-2027-009999",
                requester_employee_id="EMP-000002",
                target_employee_id="EMP-000004",
                requester_assignment_id="ASG-000002",
                target_assignment_id="ASG-000003",
                reason="Should never apply",
                status="REQUESTED",
                requester_agreed=True,
                target_agreed=True,
            )
        )
        db.commit()
    response = client.put("/api/swaps/SWP-2027-009999/apply", headers=manager_headers, json={})
    assert response.status_code == 409
    assert "approval" in response.json()["error"]["message"].lower()
