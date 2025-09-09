import os
import pytest

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

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


def test_operator_report_page(app_instance):
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/operator")
        assert resp.status_code == 200
        assert b"Operator Report" in resp.data


def test_export_operator_report(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        # Sample AOI rows to drive the aggregation
        aoi_rows = [
            {
                "Date": "2024-07-01",
                "Operator": "Alice",
                "Assembly": "A1",
                "Quantity Inspected": 10,
                "Quantity Rejected": 1,
            },
            {
                "Date": "2024-07-02",
                "Operator": "Alice",
                "Assembly": "A2",
                "Quantity Inspected": 20,
                "Quantity Rejected": 2,
            },
        ]
        from app.main import routes

        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/operator/export?format=html&start_date=2024-07-01&end_date=2024-07-02&operator=Alice"
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Total Boards" in html
        assert "A1" in html
        assert "2024-07-01" in html
