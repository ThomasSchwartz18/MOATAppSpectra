import os

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from app import create_app


@pytest.fixture
def app_instance(monkeypatch):
    monkeypatch.setattr(app_module, "create_client", lambda url, key: object())
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")
    app = create_app()
    return app


def _login(client):
    with client.session_transaction() as session:
        session["username"] = "tester"


def _make_fetch(rows, error=None):
    return lambda *args, rows=rows, error=error, **kwargs: (rows, error)


def _current_day():
    return datetime.now(timezone.utc).date()


def _moat_preview_patch():
    today = _current_day()
    rows = [
        {
            "Model Name": "Asm1 SMT",
            "Total Boards": 120,
            "FalseCall Parts": 6,
            "Report Date": today.isoformat(),
        },
        {
            "Model Name": "Asm2 SMT",
            "Total Boards": 80,
            "FalseCall Parts": 4,
            "Report Date": (today - timedelta(days=1)).isoformat(),
        },
    ]
    return {"fetch_recent_moat": _make_fetch(rows)}


def _aoi_preview_patch():
    today = _current_day()
    rows = [
        {
            "Date": today.isoformat(),
            "Quantity Inspected": 150,
            "Quantity Rejected": 5,
        },
        {
            "Date": (today - timedelta(days=1)).isoformat(),
            "Quantity Inspected": 140,
            "Quantity Rejected": 4,
        },
    ]
    return {"fetch_aoi_reports": _make_fetch(rows)}


def _fi_preview_patch():
    today = _current_day()
    rows = [
        {
            "Date": today.isoformat(),
            "Quantity Inspected": 110,
            "Quantity Rejected": 3,
        },
        {
            "Date": (today - timedelta(days=1)).isoformat(),
            "Quantity Inspected": 115,
            "Quantity Rejected": 2,
        },
    ]
    return {"fetch_fi_reports": _make_fetch(rows)}


def _daily_preview_patch():
    today = _current_day()
    rows = [
        {
            "aoi_Date": today.isoformat(),
            "aoi_Quantity Inspected": 160,
            "aoi_Quantity Rejected": 6,
        },
        {
            "fi_Date": (today - timedelta(days=1)).isoformat(),
            "fi_Quantity Inspected": 130,
            "fi_Quantity Rejected": 4,
        },
    ]
    return {"fetch_combined_reports": _make_fetch(rows)}


def _forecast_preview_patch():
    today = _current_day()
    moat_rows = [
        {
            "Model Name": "Asm1 SMT",
            "Total Boards": 200,
            "FalseCall Parts": 10,
            "Report Date": (today - timedelta(days=1)).isoformat(),
        }
    ]
    aoi_rows = [
        {
            "Assembly": "Asm1",
            "Program": "SMT",
            "Quantity Inspected": 180,
            "Quantity Rejected": 8,
            "Date": today.isoformat(),
        }
    ]
    return {
        "fetch_recent_moat": _make_fetch(moat_rows),
        "fetch_aoi_reports": _make_fetch(aoi_rows),
    }


PREVIEW_CASES = [
    ("/moat_preview", _moat_preview_patch),
    ("/aoi_preview", _aoi_preview_patch),
    ("/fi_preview", _fi_preview_patch),
    ("/daily_reports_preview", _daily_preview_patch),
    ("/forecast_preview", _forecast_preview_patch),
]


@pytest.mark.parametrize("endpoint, patch_factory", PREVIEW_CASES)
def test_home_dashboard_previews_return_expected_fields(
    app_instance, monkeypatch, endpoint, patch_factory
):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        for attr, replacement in patch_factory().items():
            monkeypatch.setattr(routes, attr, replacement)

        _login(client)
        response = client.get(endpoint)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert "labels" in payload
    assert {"values", "yields"} & payload.keys()
    assert "start_date" in payload
    assert "end_date" in payload
