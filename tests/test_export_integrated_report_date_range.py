import os
import pytest

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

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


def test_export_integrated_report_respects_date_range(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        combined = [
            {
                "Date": "2024-07-01",
                "Assembly": "ASM1",
                "Quantity Inspected": 100,
                "Quantity Rejected": 5,
            },
            {
                "Date": "2024-08-01",
                "Assembly": "ASM2",
                "Quantity Inspected": 50,
                "Quantity Rejected": 2,
            },
        ]
        aoi_rows = [
            {
                "Date": "2024-07-01",
                "Operator": "Alice",
                "Quantity Inspected": 100,
                "Quantity Rejected": 5,
            },
            {
                "Date": "2024-08-01",
                "Operator": "Bob",
                "Quantity Inspected": 100,
                "Quantity Rejected": 5,
            },
        ]
        moat_rows = [
            {
                "report_date": "2024-07-01",
                "Model": "M1",
                "FalseCall Parts": 10,
                "Total Boards": 1,
                "Total Parts": 100,
                "NG Parts": 2,
            },
            {
                "report_date": "2024-08-01",
                "Model": "M2",
                "FalseCall Parts": 20,
                "Total Boards": 1,
                "Total Parts": 100,
                "NG Parts": 4,
            },
        ]
        monkeypatch.setattr(routes, "fetch_combined_reports", lambda: (combined, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        monkeypatch.setattr(routes, "fetch_moat", lambda: (moat_rows, None))
        # Avoid heavy chart generation during test
        monkeypatch.setattr(routes, "_generate_report_charts", lambda payload: {
            "yieldTrendImg": "",
            "operatorRejectImg": "",
            "modelFalseCallsImg": "",
            "fcVsNgRateImg": "",
            "fcNgRatioImg": "",
        })
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/integrated/export?start_date=2024-07-01&end_date=2024-07-31&format=html"
        )
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        # Only in-range data should be present
        assert "2024-07-01" in html
        assert "2024-08-01" not in html
        assert "Alice" in html
        assert "Bob" not in html
        assert "M1" in html
        assert "M2" not in html
        # PDF export should succeed as well
        resp_pdf = client.get(
            "/reports/integrated/export?start_date=2024-07-01&end_date=2024-07-31&format=pdf"
        )
        assert resp_pdf.status_code == 200
        assert resp_pdf.mimetype == "application/pdf"
        assert len(resp_pdf.data) > 1000
