import os
import pytest

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

import app as app_module
from app import create_app

# Sample AOI rows used by multiple tests
SAMPLE_AOI_ROWS = [
    {
        "Date": "2024-07-01",
        "Operator": "Alice",
        "Assembly": "A1",
        "Program": "P1",
        "Quantity Inspected": 10,
        "Quantity Rejected": 1,
    },
    {
        "Date": "2024-07-01",
        "Operator": "Bob",
        "Assembly": "A1",
        "Program": "P1",
        "Quantity Inspected": 15,
        "Quantity Rejected": 2,
    },
    {
        "Date": "2024-07-02",
        "Operator": "Alice",
        "Assembly": "A2",
        "Program": "P2",
        "Quantity Inspected": 20,
        "Quantity Rejected": 2,
    },
    {
        "Date": "2024-07-02",
        "Operator": "Bob",
        "Assembly": "A2",
        "Program": "P2",
        "Quantity Inspected": 25,
        "Quantity Rejected": 3,
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


def test_operator_report_page(app_instance):
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/operator")
        assert resp.status_code == 200
        assert b"Operator Report" in resp.data
        # Verify the operator dropdown placeholder is rendered
        assert b"operator-wrapper" in resp.data


def test_export_operator_report(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        monkeypatch.setattr(
            routes, "fetch_aoi_reports", lambda: (SAMPLE_AOI_ROWS, None)
        )
        monkeypatch.setattr(routes, "fetch_combined_reports", lambda: ([], None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/operator/export?format=html&start_date=2024-07-01&end_date=2024-07-02&operator=Alice"
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Total Boards" in html
        # Assemblies for Alice are A1 and A2
        assert "A1" in html and "A2" in html
        assert "2024-07-01" in html


def test_api_operator_report_filters_and_aggregates(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        monkeypatch.setattr(
            routes, "fetch_aoi_reports", lambda: (SAMPLE_AOI_ROWS, None)
        )
        combined_rows = [
            {
                "aoi_Date": "2024-07-01",
                "aoi_Operator": "Alice",
                "aoi_Assembly": "A1",
                "aoi_Program": "P1",
                "aoi_Quantity Inspected": 10,
                "fi_Quantity Rejected": 1,
            },
            {
                "aoi_Date": "2024-07-02",
                "aoi_Operator": "Alice",
                "aoi_Assembly": "A2",
                "aoi_Program": "P2",
                "aoi_Quantity Inspected": 20,
                "fi_Quantity Rejected": 2,
            },
        ]
        monkeypatch.setattr(routes, "fetch_combined_reports", lambda: (combined_rows, None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/api/reports/operator?start_date=2024-07-01&end_date=2024-07-02&operator=Alice"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["daily"]["dates"] == ["2024-07-01", "2024-07-02"]
        assert data["daily"]["inspected"] == [10.0, 20.0]
        assert data["daily"]["rejectRates"] == [10.0, 10.0]
        assert data["summary"] == {
            "totalBoards": 30.0,
            "avgPerShift": 15.0,
            "avgRejectRate": 10.0,
            "avgBoards": 30.0,
        }
        assert data["assemblies"] == [
            {
                "assembly": "A2",
                "inspected": 20.0,
                "rejected": 2.0,
                "fiRejectRate": 10.0,
            },
            {
                "assembly": "A1",
                "inspected": 10.0,
                "rejected": 1.0,
                "fiRejectRate": 10.0,
            },
        ]


def test_operator_cover_page(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        sample_payload = {
            "daily": {"dates": ["2024-07-01"], "inspected": [10.0], "rejectRates": [5.0]},
            "assemblies": [{"assembly": "A1", "inspected": 10.0}],
            "summary": {
                "totalBoards": 10.0,
                "avgPerShift": 10.0,
                "avgRejectRate": 5.0,
                "avgBoards": 10.0,
            },
        }

        monkeypatch.setattr(
            routes, "build_operator_report_payload", lambda start, end, operator: sample_payload
        )
        monkeypatch.setattr(routes, "_generate_operator_report_charts", lambda payload: {})
        monkeypatch.setattr(routes, "fetch_combined_reports", lambda: ([], None))

        with client.session_transaction() as sess:
            sess["username"] = "tester"

        resp = client.get(
            "/reports/operator/export?format=html&show_cover=true&show_summary=true&operator=Alice"
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "cover-page" in html
        assert "/static/images/company-logo.png" in html
        assert "Alice" in html

        resp = client.get(
            "/reports/operator/export?format=html&show_cover=false&show_summary=true&operator=Alice"
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "cover-page" not in html
