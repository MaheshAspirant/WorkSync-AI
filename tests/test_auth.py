from __future__ import annotations


def test_admin_login_and_me(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["role"] == "ADMIN"
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


def test_invalid_login_returns_401(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401
    assert "error" in response.json()


def test_employee_cannot_create_employee(client, employee_headers):
    response = client.post(
        "/api/employees",
        headers=employee_headers,
        json={
            "team_id": "TEAM-001",
            "first_name": "Nope",
            "last_name": "Nope",
            "email": "nope@worksync.ai",
            "job_title": "Associate",
            "hire_date": "2025-01-01",
        },
    )
    assert response.status_code == 403


def test_employee_cannot_read_other_team_employee(client, employee_headers):
    response = client.get("/api/employees/EMP-000008", headers=employee_headers)
    assert response.status_code == 403


def test_employee_directory_is_scoped_to_team(client, employee_headers):
    response = client.get("/api/employees?page_size=100", headers=employee_headers)
    assert response.status_code == 200
    team_ids = {item["team_id"] for item in response.json()["items"]}
    assert team_ids == {"TEAM-001"}


def test_teams_are_scoped_for_manager(client, manager_headers):
    response = client.get("/api/teams?page_size=100", headers=manager_headers)
    assert response.status_code == 200
    assert [team["team_id"] for team in response.json()["items"]] == ["TEAM-001"]
