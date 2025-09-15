import os
from datetime import datetime, timedelta

import pytest

import app as app_module
from app import create_app


os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")


@pytest.fixture
def app_instance(monkeypatch):
    monkeypatch.setattr(app_module, "create_client", lambda url, key: object())
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")
    app = create_app()
    return app


def _login(client):
    with client.session_transaction() as sess:
        sess["username"] = "tester"


def _recent_dates(count=3):
    today = datetime.utcnow().date()
    return [today - timedelta(days=offset) for offset in range(count)]


def _assert_preview_keys(data):
    for key in ("labels", "values", "start_date", "end_date"):
        assert key in data


def test_moat_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        d0, d1 = _recent_dates(2)
        moat_rows = [
            {
                "Model Name": "Asm1 SMT",
                "FalseCall Parts": 5,
                "Total Boards": 100,
                "Report Date": d0.isoformat(),
            },
            {
                "Model Name": "Asm2 SMT",
                "falsecall_parts": 2,
                "total_boards": 50,
                "report_date": d1.isoformat(),
            },
        ]
        monkeypatch.setattr(routes, "fetch_recent_moat", lambda: (moat_rows, None))
        _login(client)
        resp = client.get("/moat_preview")
        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert set(data["labels"]) == {"Asm1 SMT", "Asm2 SMT"}
        assert len(data["labels"]) == len(data["values"])


def test_aoi_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        d0, d1 = _recent_dates(2)
        aoi_rows = [
            {
                "Date": d0.isoformat(),
                "Quantity Inspected": 100,
                "Quantity Rejected": 5,
            },
            {
                "date": d1.isoformat(),
                "quantity_inspected": 80,
                "quantity_rejected": 4,
            },
        ]
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        _login(client)
        resp = client.get("/aoi_preview")
        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert len(data["labels"]) == len(data["values"])


def test_fi_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        d0, d1 = _recent_dates(2)
        fi_rows = [
            {
                "Date": d0.isoformat(),
                "Quantity Inspected": 120,
                "Quantity Rejected": 6,
            },
            {
                "date": d1.isoformat(),
                "quantity_inspected": 150,
                "quantity_rejected": 3,
            },
        ]
        monkeypatch.setattr(routes, "fetch_fi_reports", lambda: (fi_rows, None))
        _login(client)
        resp = client.get("/fi_preview")
        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert len(data["labels"]) == len(data["values"])


def test_daily_reports_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        d0, d1, d2 = _recent_dates(3)
        combined_rows = [
            {
                "aoi_Date": d0.isoformat(),
                "aoi_Quantity Inspected": 90,
                "aoi_Quantity Rejected": 5,
            },
            {
                "Date": d1.isoformat(),
                "Quantity Inspected": 110,
                "Quantity Rejected": 4,
            },
            {
                "fi_Date": d2.isoformat(),
                "fi_Quantity Inspected": 100,
                "fi_Quantity Rejected": 6,
            },
        ]
        monkeypatch.setattr(
            routes, "fetch_combined_reports", lambda: (combined_rows, None)
        )
        _login(client)
        resp = client.get("/daily_reports_preview")
        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert "avg_yield" in data
        assert len(data["labels"]) == len(data["values"])


def test_forecast_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        d0, d1 = _recent_dates(2)
        moat_rows = [
            {
                "Model Name": "Asm1 SMT",
                "Total Boards": 100,
                "FalseCall Parts": 5,
                "Report Date": d0.isoformat(),
            },
            {
                "Model Name": "Asm2 SMT",
                "Total Boards": 80,
                "FalseCall Parts": 4,
                "Report Date": d1.isoformat(),
            },
        ]
        aoi_rows = [
            {
                "Assembly": "Asm1",
                "Program": "SMT",
                "Quantity Inspected": 90,
                "Quantity Rejected": 3,
                "Date": d0.isoformat(),
            },
            {
                "Assembly": "Asm2",
                "Program": "SMT",
                "Quantity Inspected": 70,
                "Quantity Rejected": 2,
                "Date": d1.isoformat(),
            },
        ]
        monkeypatch.setattr(routes, "fetch_recent_moat", lambda: (moat_rows, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        _login(client)
        resp = client.get("/forecast_preview")
        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert data["labels"]
        assert len(data["labels"]) == len(data["values"])
