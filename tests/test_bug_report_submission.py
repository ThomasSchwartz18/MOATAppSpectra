import os
import sys
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


def test_bug_report_prefers_supabase_id_for_supabase_user(app_client, monkeypatch):
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

    payload = response.get_json()
    assert "reporter_id" not in payload
    assert payload["reporter_display_name"] == "ADMIN"
