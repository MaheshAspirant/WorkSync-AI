from __future__ import annotations


def test_dashboard_metrics_are_calculated(client, admin_headers):
    response = client.get("/api/analytics/dashboard", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    for field in (
        "total_employees",
        "total_teams",
        "total_shifts",
        "coverage_pct",
        "skill_coverage_pct",
        "total_overtime_hours",
        "fairness_score",
        "schedule_validity_pct",
    ):
        assert field in body
    assert body["total_employees"] == 9
    assert body["total_teams"] == 2
    assert 0 <= body["coverage_pct"] <= 100
    assert 0 <= body["fairness_score"] <= 100
    assert 0 <= body["schedule_validity_pct"] <= 100


def test_coverage_fairness_and_leave_analytics(client, admin_headers):
    coverage = client.get("/api/analytics/coverage", headers=admin_headers)
    assert coverage.status_code == 200
    assert coverage.json()["required_positions"] > 0

    fairness = client.get("/api/analytics/fairness", headers=admin_headers)
    assert fairness.status_code == 200
    assert "fairness_score" in fairness.json()

    leave = client.get("/api/analytics/leave", headers=admin_headers)
    assert leave.status_code == 200
    assert "approval_rate" in leave.json()


def test_employee_cannot_access_global_analytics(client, employee_headers):
    response = client.get("/api/analytics/dashboard", headers=employee_headers)
    assert response.status_code == 403


def test_admin_validation_report(client, admin_headers):
    response = client.get("/api/admin/validation", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"PASS", "FAIL"}
    assert body["checks"]
