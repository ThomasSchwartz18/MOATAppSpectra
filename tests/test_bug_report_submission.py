import os
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module
from app import create_app
from app.main import routes as routes_module


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setattr(app_module, "create_client", lambda url, key: object())
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")
    app = create_app()
    app.testing = True
    client = app.test_client()
    return app, client


def test_bug_report_uses_supabase_account_id(app_client, monkeypatch):
    app, client = app_client

    recorded = {}

    def fake_insert(record):
        recorded["record"] = record
        stored = dict(record)
        stored.setdefault("id", 1)
        return [stored], None

    def fake_fetch(username):
        recorded["fetched_username"] = username
        return {
            "id": 9876,
            "username": username,
            "display_name": "Ana Analyst",
            "auth_user_id": "00000000-0000-0000-0000-000000000123",
            "auth_user": {"id": "00000000-0000-0000-0000-000000000123"},
        }, None

    monkeypatch.setattr(routes_module, "insert_bug_report", fake_insert)
    monkeypatch.setattr(routes_module, "fetch_app_user_credentials", fake_fetch)

    with client.session_transaction() as session:
        session["username"] = "analyst"
        session["user_id"] = "app-user-id"

    response = client.post(
        "/bug-reports",
        json={"title": "Printer jam", "description": "Paper jams on tray 2."},
    )

    assert response.status_code == 201
    assert recorded["fetched_username"] == "analyst"
    inserted_record = recorded["record"]
    assert inserted_record["reporter_id"] == "9876"
    assert inserted_record["reporter_name"] == "Ana Analyst"

    payload = response.get_json()
    assert payload["reporter_id"] == "9876"
    assert payload["reporter_display_name"] == "Ana Analyst"


def test_bug_report_omits_reporter_id_for_environment_user(app_client, monkeypatch):
    app, client = app_client

    recorded = {}

    def fake_insert(record):
        recorded["record"] = record
        stored = dict(record)
        stored.setdefault("id", 2)
        return [stored], None

    def fake_fetch(username):
        recorded["fetched_username"] = username
        return None, None

    monkeypatch.setattr(routes_module, "insert_bug_report", fake_insert)
    monkeypatch.setattr(routes_module, "fetch_app_user_credentials", fake_fetch)

    with client.session_transaction() as session:
        session["username"] = "ADMIN"
        session["role"] = "ADMIN"

    response = client.post(
        "/bug-reports",
        json={"title": "Missing data", "description": "Report tiles are empty."},
    )

    assert response.status_code == 201
    assert recorded["fetched_username"] == "ADMIN"
    inserted_record = recorded["record"]
    assert "reporter_id" not in inserted_record
    assert inserted_record["reporter_name"] == "ADMIN"

    payload = response.get_json()
    assert "reporter_id" not in payload
    assert payload["reporter_display_name"] == "ADMIN"


def test_bug_report_uses_supabase_id_for_orphaned_account(
    app_client, monkeypatch
):
    app, client = app_client

    recorded = {}

    def fake_insert(record):
        recorded["record"] = record
        stored = dict(record)
        stored.setdefault("id", 3)
        return [stored], None

    def fake_fetch(username):
        recorded["fetched_username"] = username
        return {
            "id": 777,
            "username": username,
            "display_name": "Ophelia Ops",
            # Simulate a Supabase row that is no longer linked to auth.users.
            "auth_user_id": None,
        }, None

    monkeypatch.setattr(routes_module, "insert_bug_report", fake_insert)
    monkeypatch.setattr(routes_module, "fetch_app_user_credentials", fake_fetch)

    with client.session_transaction() as session:
        session["username"] = "orphaned"

    response = client.post(
        "/bug-reports",
        json={
            "title": "Missing auth",
            "description": "Account removed from auth.users",
        },
    )

    assert response.status_code == 201
    assert recorded["fetched_username"] == "orphaned"
    inserted_record = recorded["record"]
    assert inserted_record["reporter_id"] == "777"
    assert inserted_record["reporter_name"] == "Ophelia Ops"

    payload = response.get_json()
    assert payload["reporter_id"] == "777"
    assert payload["reporter_display_name"] == "Ophelia Ops"


def test_bug_report_falls_back_to_session_user_id(app_client, monkeypatch):
    app, client = app_client

    recorded = {}

    def fake_insert(record):
        recorded["record"] = record
        stored = dict(record)
        stored.setdefault("id", 4)
        return [stored], None

    def fake_fetch(username):
        recorded["fetched_username"] = username
        return {
            "id": None,
            "username": username,
            "display_name": "Sasha Session",
            "auth_user_id": None,
        }, None

    monkeypatch.setattr(routes_module, "insert_bug_report", fake_insert)
    monkeypatch.setattr(routes_module, "fetch_app_user_credentials", fake_fetch)

    with client.session_transaction() as session:
        session["username"] = "sessioned"
        session["user_id"] = 4321

    response = client.post(
        "/bug-reports",
        json={
            "title": "Feature glitch",
            "description": "UI freezes intermittently",
        },
    )

    assert response.status_code == 201
    assert recorded["fetched_username"] == "sessioned"
    inserted_record = recorded["record"]
    assert inserted_record["reporter_id"] == "4321"
    assert inserted_record["reporter_name"] == "Sasha Session"

    payload = response.get_json()
    assert payload["reporter_id"] == "4321"
    assert payload["reporter_display_name"] == "Sasha Session"


def test_admin_bug_report_view_shows_reporter_name(app_client, monkeypatch):
    app, client = app_client

    class DummyCursor:
        def fetchall(self):
            return []

        def fetchone(self):
            return None

    class DummyConnection:
        def execute(self, *args, **kwargs):
            return DummyCursor()

    class DummyTracker:
        def _connect(self):
            return nullcontext(DummyConnection())

    def fake_fetch_bug_reports(filters=None):
        record = {
            "id": 55,
            "title": "Broken widget",
            "status": "open",
            "priority": "High",
            "reporter_name": "Carla Candidate",
            "created_at": "2024-01-01T12:00:00+00:00",
            "updated_at": "2024-01-02T12:00:00+00:00",
        }
        return [record], None

    monkeypatch.setattr(routes_module, "_get_tracker", lambda: DummyTracker())
    monkeypatch.setattr(routes_module, "fetch_bug_reports", fake_fetch_bug_reports)
    monkeypatch.setattr(routes_module, "_fetch_configured_users", lambda: ([], None))

    with client.session_transaction() as session:
        session["username"] = "ADMIN"
        session["role"] = "ADMIN"

    response = client.get("/analysis/tracker-logs")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Carla Candidate" in html
