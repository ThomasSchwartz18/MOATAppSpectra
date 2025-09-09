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


def test_operator_report_api(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        aoi_rows = [
            {
                "Date": "2024-07-01",
                "Operator": "Alice",
                "Assembly": "A1",
                "Quantity Inspected": 10,
                "Quantity Rejected": 1,
            },
            {
                "Date": "2024-07-01",
                "Operator": "Alice",
                "Assembly": "A2",
                "Quantity Inspected": 20,
                "Quantity Rejected": 2,
            },
            {
                "Date": "2024-07-02",
                "Operator": "Alice",
                "Assembly": "A1",
                "Quantity Inspected": 30,
                "Quantity Rejected": 3,
            },
            {
                "Date": "2024-07-02",
                "Operator": "Bob",
                "Assembly": "A1",
                "Quantity Inspected": 40,
                "Quantity Rejected": 4,
            },
        ]
        combined_rows = [
            {
                "aoi_Date": "2024-07-01",
                "aoi_Operator": "Alice",
                "aoi_Assembly": "A1",
                "aoi_Quantity Inspected": 10,
                "fi_Quantity Rejected": 1,
            },
            {
                "aoi_Date": "2024-07-02",
                "aoi_Operator": "Alice",
                "aoi_Assembly": "A1",
                "aoi_Quantity Inspected": 30,
                "fi_Quantity Rejected": 2,
            },
        ]
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        monkeypatch.setattr(routes, "fetch_combined_reports", lambda: (combined_rows, None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/api/reports/operator?start_date=2024-07-01&end_date=2024-07-02&operator=Alice"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["daily"]["dates"] == ["2024-07-01", "2024-07-02"]
        assert data["daily"]["inspected"] == [30.0, 30.0]
        assert data["daily"]["rejectRates"] == [10.0, 10.0]
        assert data["summary"] == {
            "totalBoards": 60.0,
            "avgPerShift": 30.0,
            "avgRejectRate": 10.0,
            "avgBoards": 60.0,
        }
        assert data["assemblies"] == [
            {
                "assembly": "A1",
                "inspected": 40.0,
                "rejected": 4.0,
                "fiRejectRate": 7.5,
            },
            {
                "assembly": "A2",
                "inspected": 20.0,
                "rejected": 2.0,
                "fiRejectRate": None,
            },
        ]
