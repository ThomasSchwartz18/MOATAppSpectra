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


def test_operator_stats_from_aoi_reports(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        combined = []
        aoi_rows = [
            {
                "Date": "2024-07-01",
                "Operator": "Alice",
                "Program": "Alpha",
                "Quantity Inspected": 100,
                "Quantity Rejected": 5,
            }
        ]
        monkeypatch.setattr(routes, "fetch_combined_reports", lambda: (combined, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        monkeypatch.setattr(routes, "fetch_moat", lambda: ([], None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/api/reports/integrated")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["operators"] == [
            {"name": "Alice", "inspected": 100.0, "rejected": 5.0, "rate": 5.0}
        ]
