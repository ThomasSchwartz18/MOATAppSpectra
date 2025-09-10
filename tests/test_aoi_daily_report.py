import os
import re
import sys
import pytest

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import app as app_module
from app import create_app
from app.main import routes


@pytest.fixture
def app_instance(monkeypatch):
    monkeypatch.setattr(app_module, "create_client", lambda url, key: object())
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")
    app = create_app()
    return app


def _mock_payload(monkeypatch):
    sample_payload = {
        "shiftImg": "img",
        "shift1_total": 10,
        "shift1_reject_pct": 1,
        "shift2_total": 20,
        "shift2_reject_pct": 2,
        "shift_total_diff": 10,
        "shift_reject_pct_diff": 1,
        "assemblies": [
            {
                "assembly": "Asm1",
                "yield": 95.0,
                "past4Avg": 96.0,
                "operators": ["Op1"],
                "boards": 5,
                "currentRejects": 0,
                "pastRejectsAvg": 1,
                "fiTypicalRejects": 2,
            }
        ],
        "shift1": [
            {
                "operator": "Op1",
                "assembly": "Asm1",
                "job": "J1",
                "inspected": 5,
                "rejected": 0,
            }
        ],
        "shift2": [
            {
                "operator": "Op2",
                "assembly": "Asm2",
                "job": "J2",
                "inspected": 10,
                "rejected": 1,
            }
        ],
    }
    monkeypatch.setattr(
        routes,
        "build_aoi_daily_report_payload",
        lambda day, operator, assembly: sample_payload,
    )
    monkeypatch.setattr(routes, "_generate_aoi_daily_report_charts", lambda payload: {})



def test_export_aoi_daily_report_cover_fields(app_instance, monkeypatch):
    _mock_payload(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/aoi_daily/export?date=2024-06-01&show_cover=1&contact=help@example.com"
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "report_range:</b> 2024-06-01 - 2024-06-01" in html
        assert "&lt;help@example.com&gt;" in html
        assert re.search(
            r"generated_at:</b> \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} EST", html
        )


def test_export_aoi_daily_report_default_contact(app_instance, monkeypatch):
    _mock_payload(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/aoi_daily/export?date=2024-06-01&show_cover=1")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "&lt;tschawtz@4spectra.com&gt;" in html


def test_shift_chart_description_rendered(app_instance, monkeypatch):
    sample_payload = {
        "shift1_total": 10,
        "shift1_reject_pct": 1,
        "shift2_total": 20,
        "shift2_reject_pct": 2,
        "shift_total_diff": 10,
        "shift_reject_pct_diff": 1,
        "shiftTotals": {
            "shift1": {"inspected": 10},
            "shift2": {"inspected": 20},
        },
        "assemblies": [{"assembly": "Asm1", "yield": 95.0, "past4Avg": 96.0}],
        "shift1": [
            {
                "operator": "Op1",
                "assembly": "Asm1",
                "job": "J1",
                "inspected": 5,
                "rejected": 0,
            }
        ],
        "shift2": [
            {
                "operator": "Op2",
                "assembly": "Asm2",
                "job": "J2",
                "inspected": 10,
                "rejected": 1,
            }
        ],
    }
    monkeypatch.setattr(
        routes, "build_aoi_daily_report_payload", lambda day, operator, assembly: sample_payload
    )
    monkeypatch.setattr(routes, "plt", None)

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/aoi_daily/export?date=2024-06-01")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert (
            "2nd shift inspected 10 more boards than 1st shift." in html
            and "chart-desc" in html
        )


def test_assembly_detail_rendered(app_instance, monkeypatch):
    sample_payload = {
        "assemblies": [
            {
                "assembly": "Asm1",
                "yield": 90.0,
                "past4Avg": 95.0,
                "operators": ["Op1", "Op2"],
                "boards": 20,
                "currentRejects": 2,
                "pastRejectsAvg": 1.5,
                "fiTypicalRejects": 1,
            }
        ],
        "shift1": [],
        "shift2": [],
        "shiftTotals": {
            "shift1": {"inspected": 0, "rejected": 0},
            "shift2": {"inspected": 0, "rejected": 0},
        },
    }
    monkeypatch.setattr(
        routes, "build_aoi_daily_report_payload", lambda day, operator, assembly: sample_payload
    )
    monkeypatch.setattr(routes, "_generate_aoi_daily_report_charts", lambda payload: {})

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/aoi_daily/export?date=2024-06-01")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Asm1" in html
        assert "Operators:</strong> Op1, Op2" in html
        assert "Boards Processed:</strong> 20" in html
        assert "Current Yield %</td><td>90.00" in html
        assert re.search(r"Historical Yield %</td><td>\s*95.00", html)
        assert "Current AOI Rejects</td><td>2" in html
        assert re.search(r"Past AOI Rejects \(Avg\)</td><td>\s*1.5", html)
        assert "Typical FI Rejects</td><td>1" in html


def test_toc_after_shift_summary(app_instance, monkeypatch):
    _mock_payload(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/aoi_daily/export?date=2024-06-01")
        assert resp.status_code == 200
        html = resp.data.decode()
        shift_idx = html.index("Shift Comparison")
        toc_idx = html.index("Table of Contents")
        assert shift_idx < toc_idx


def test_historical_yield_uses_four_jobs(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        rows = [
            {
                "Date": "2024-06-05",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J6",
                "Quantity Inspected": 100,
                "Quantity Rejected": 0,
                "Shift": "1",
            },
            {
                "Date": "2024-06-04",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J5",
                "Quantity Inspected": 100,
                "Quantity Rejected": 10,
            },
            {
                "Date": "2024-06-03",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J4",
                "Quantity Inspected": 100,
                "Quantity Rejected": 20,
            },
            {
                "Date": "2024-06-02",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J3",
                "Quantity Inspected": 100,
                "Quantity Rejected": 30,
            },
            {
                "Date": "2024-06-01",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J2",
                "Quantity Inspected": 100,
                "Quantity Rejected": 40,
            },
            {
                "Date": "2024-05-31",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J1",
                "Quantity Inspected": 100,
                "Quantity Rejected": 50,
            },
        ]
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (rows, None))
        monkeypatch.setattr(routes, "fetch_fi_reports", lambda: ([], None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/api/reports/aoi_daily?date=2024-06-05")
        assert resp.status_code == 200
        data = resp.get_json()
        asm = data["assemblies"][0]
        assert asm["past4Avg"] == pytest.approx(75.0)
        assert asm["pastRejectsAvg"] == pytest.approx(25.0)
