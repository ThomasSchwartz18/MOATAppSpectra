import os
import math
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


def test_aoi_grades_customer_yield_case_insensitive(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        data = [
            {
                "aoi_Customer": "PG LifeLink",
                "aoi_Quantity Inspected": 100,
                "aoi_Quantity Rejected": 10,
                "fi_Quantity Rejected": 5,
            },
            {
                "aoi_Customer": "pg lifelink",
                "aoi_Quantity Inspected": 50,
                "aoi_Quantity Rejected": 5,
                "fi_Quantity Rejected": 2,
            },
        ]
        monkeypatch.setattr(routes, "fetch_combined_reports", lambda: (data, None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/analysis/aoi/grades/customer_yield")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["labels"] == ["PG LifeLink"]
        assert math.isclose(payload["yields"][0], 85.3333333333, rel_tol=1e-9)


def test_daily_data_customer_rate_case_insensitive(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        rows = [
            {
                "Date": "2024-07-01",
                "Customer": "PG LifeLink",
                "Quantity Inspected": 10,
                "Quantity Rejected": 2,
            },
            {
                "Date": "2024-07-01",
                "Customer": "pg lifelink",
                "Quantity Inspected": 10,
                "Quantity Rejected": 1,
            },
            {
                "Date": "2024-07-01",
                "Customer": "Other",
                "Quantity Inspected": 10,
                "Quantity Rejected": 1,
            },
        ]
        monkeypatch.setattr(routes, "fetch_fi_reports", lambda: (rows, None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/analysis/fi/data?view=customer_rate&customers=pg lifelink")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["labels"] == ["PG LifeLink"]
        assert math.isclose(payload["rates"][0], 15.0, rel_tol=1e-9)
