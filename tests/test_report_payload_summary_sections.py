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


def test_summary_sections(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        combined = []
        aoi_rows = [
            {
                "Date": "2024-01-01",
                "Operator": "Op1",
                "Assembly": "ASM1",
                "Job Number": "J1",
                "Quantity Inspected": 100,
                "Quantity Rejected": 10,
            },
            {
                "Date": "2024-01-02",
                "Operator": "Op2",
                "Assembly": "ASM2",
                "Job Number": "J2",
                "Quantity Inspected": 100,
                "Quantity Rejected": 0,
            },
        ]
        moat_rows = [
            {
                "Report Date": "2024-01-01",
                "Model": "ASM1",
                "FalseCall Parts": 5,
                "Total Boards": 1,
                "Total Parts": 10,
                "NG Parts": 1,
            }
        ]
        monkeypatch.setattr(routes, "fetch_combined_reports", lambda: (combined, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        monkeypatch.setattr(routes, "fetch_moat", lambda: (moat_rows, None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/api/reports/integrated")
        assert resp.status_code == 200
        data = resp.get_json()

        kpis = data["summary_kpis"]
        assert isinstance(kpis, list)
        first = kpis[0]
        assert {"label", "value", "target", "delta"}.issubset(first.keys())
        assert first["delta"] == pytest.approx(first["value"] - first["target"])

        assert "executive_summary" in data
        assert data["executive_summary"]["kpis"] == kpis
        assert "programQueue" not in data["executive_summary"]
        assert "program_queue" not in data
        assert "charts" in data
        assert "top_tables" in data
