import os
import math
import pytest

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

import app as app_module
from app import create_app

SAMPLE_AOI_ROWS = [
    {
        "Date": "2024-07-01",
        "Shift": "1st",
        "Operator": "Alice",
        "Assembly": "ASM1",
        "Job Number": "J100",
        "Quantity Inspected": 50,
        "Quantity Rejected": 5,
    },
    {
        "Date": "2024-07-01",
        "Shift": "2nd",
        "Operator": "Bob",
        "Assembly": "ASM2",
        "Job Number": "J200",
        "Quantity Inspected": 40,
        "Quantity Rejected": 2,
    },
    {
        "Date": "2024-06-30",
        "Shift": "1st",
        "Operator": "Alice",
        "Assembly": "ASM2",
        "Job Number": "J199",
        "Quantity Inspected": 60,
        "Quantity Rejected": 3,
    },
    {
        "Date": "2024-06-29",
        "Shift": "2nd",
        "Operator": "Bob",
        "Assembly": "ASM2",
        "Job Number": "J198",
        "Quantity Inspected": 30,
        "Quantity Rejected": 0,
    },
    {
        "Date": "2024-06-28",
        "Shift": "1st",
        "Operator": "Alice",
        "Assembly": "ASM2",
        "Job Number": "J197",
        "Quantity Inspected": 20,
        "Quantity Rejected": 1,
    },
]


@pytest.fixture
def app_instance(monkeypatch):
    monkeypatch.setattr(app_module, "create_client", lambda url, key: object())
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")
    app = create_app()
    return app


def test_export_aoi_daily_report(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (SAMPLE_AOI_ROWS, None))
        monkeypatch.setattr(
            routes, "_generate_aoi_daily_report_charts", lambda payload: {"shiftImg": "/static/chart.png"}
        )
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/aoi_daily/export?format=html&date=2024-07-01&show_cover=true"
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert '<section id="cover"' in html
        assert "1st Shift Summary" in html
        assert "2nd Shift Summary" in html
        assert html.count("<table") >= 2
        assert '<img src="/static/chart.png"' in html
        assert "first run" in html


def test_aoi_daily_preview_api_shift_view(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (SAMPLE_AOI_ROWS, None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/analysis/aoi/data?view=shift&start_date=2024-07-01&end_date=2024-07-01"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["labels"] == ["2024-07-01"]
        assert data["shift1"]["accepted"] == [45]
        assert data["shift1"]["rejected"] == [5]
        assert data["shift2"]["accepted"] == [38]
        assert data["shift2"]["rejected"] == [2]
        assert math.isclose(data["shift1"]["avg_reject_rate"], 10.0, rel_tol=1e-9)
        assert math.isclose(data["shift2"]["avg_reject_rate"], 5.0, rel_tol=1e-9)
