import os
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


def test_line_report_api_returns_expected_metrics(app_instance, monkeypatch):
    ppm_rows = [
        {
            "Report Date": "2024-07-01",
            "Line": "L1",
            "Model Name": "AsmA",
            "Total Parts": 100,
            "Total Boards": 10,
            "FalseCall Parts": 5,
            "NG Parts": 15,
        },
        {
            "Report Date": "2024-07-01",
            "Line": "L2",
            "Model Name": "AsmA",
            "Total Parts": 80,
            "Total Boards": 8,
            "FalseCall Parts": 2,
            "NG Parts": 6,
        },
        {
            "Report Date": "2024-07-02",
            "Line": "L1",
            "Model Name": "AsmB",
            "Total Parts": 120,
            "Total Boards": 12,
            "FalseCall Parts": 3,
            "NG Parts": 8,
        },
    ]
    dpm_rows = [
        {
            "Report Date": "2024-07-01",
            "Line": "L1",
            "Model Name": "AsmA",
            "Total Windows": 200,
            "NG Windows": 10,
            "FalseCall Windows": 4,
            "DPM": 50000,
            "FC DPM": 20000,
        },
        {
            "Report Date": "2024-07-02",
            "Line": "L1",
            "Model Name": "AsmB",
            "Total Windows": 120,
            "NG Windows": 6,
            "FalseCall Windows": 3,
            "DPM": 50000,
            "FC DPM": 25000,
        },
        {
            "Report Date": "2024-07-01",
            "Line": "L2",
            "Model Name": "AsmA",
            "Total Windows": 80,
            "NG Windows": 5,
            "FalseCall Windows": 1,
            "DPM": 62500,
            "FC DPM": 12500,
        },
    ]

    monkeypatch.setattr(routes, "fetch_moat", lambda: (ppm_rows, None))
    monkeypatch.setattr(routes, "fetch_moat_dpm", lambda: (dpm_rows, None))

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        response = client.get(
            "/api/reports/line?start_date=2024-07-01&end_date=2024-07-05"
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["lineMetrics"]
    metrics = {item["line"]: item for item in payload["lineMetrics"]}
    assert pytest.approx(metrics["L1"]["yield"], rel=1e-3) == 93.18
    assert pytest.approx(metrics["L1"]["falseCallsPerBoard"], rel=1e-3) == 0.3636
    assert pytest.approx(metrics["L1"]["ppm"], rel=1e-4) == 36363.6363
    assert pytest.approx(metrics["L1"]["dpm"], rel=1e-4) == 50000.0
    assert pytest.approx(metrics["L1"]["boardsPerDay"], rel=1e-3) == 11.0

    assert payload["assemblyComparisons"]
    asmA = next(item for item in payload["assemblyComparisons"] if item["assembly"] == "AsmA")
    assert asmA["lines"]["L2"]["yield"] == pytest.approx(95.0)
    assert payload["benchmarking"]["bestYield"]["line"] == "L2"


def test_line_report_export_handles_pdf_error(app_instance, monkeypatch):
    monkeypatch.setattr(routes, "build_line_report_payload", lambda start, end: {
        "lineMetrics": [],
        "assemblyComparisons": [],
        "crossLine": {},
        "lineTrends": [],
        "trendInsights": {},
        "benchmarking": {"lineVsCompany": []},
        "companyAverages": {"yield": 0, "falseCallsPerBoard": 0, "ppm": 0, "dpm": 0},
    })
    monkeypatch.setattr(routes, "_generate_line_report_charts", lambda payload: {})
    monkeypatch.setattr(routes, "render_template", lambda template, **context: "<html></html>")

    def _raise_pdf_error(*args, **kwargs):
        from app.main.pdf_utils import PdfGenerationError

        raise PdfGenerationError("Install Pango")

    monkeypatch.setattr(routes, "render_html_to_pdf", _raise_pdf_error)

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/line/export?format=pdf")

    assert resp.status_code == 503
    assert resp.get_json() == {"message": "Install Pango"}
