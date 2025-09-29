import base64
import copy
import math
import os
import sys
from datetime import date

import pytest

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module
from app import create_app
from app.main import routes


def _sample_line_payload():
    return {
        "lineMetrics": [
            {
                "line": "L1",
                "windowYield": 98.5,
                "truePartYield": 97.2,
                "rawPartYield": 96.1,
                "confirmedDefects": 5,
                "windowConfirmedDefects": 6,
                "falseCallsPerBoard": 0.32,
                "falseCallPpm": 1200.5,
                "falseCallDpm": 800.1,
                "defectDpm": 500.2,
                "boardsPerDay": 18.4,
                "totalWindows": 1500,
                "totalParts": 1200,
                "totalBoards": 80,
                "falseCalls": 8,
                "ngParts": 25,
                "ngWindows": 18,
                "windowsPerBoard": 18.75,
                "defectsPerBoard": 0.225,
            }
        ],
        "assemblyComparisons": [
            {                "lines": {
                    "L1": {
                        "windowYield": 98.5,
                        "truePartYield": 97.2,
                        "rawPartYield": 96.1,
                        "falseCallsPerBoard": 0.32,
                        "falseCallPpm": 1200.5,
                        "falseCallDpm": 800.1,
                        "defectDpm": 500.2,
                        "defectMix": {"Bridge": 0.6, "Insufficient": 0.4},
                        "parts": 1200,
                        "boards": 80,
                        "windows": 1500,
                        "ngParts": 25,
                        "ngWindows": 18,
                        "falseCalls": 8,
                        "windowsPerBoard": 18.75,
                        "defectsPerBoard": 0.225,
                    }
                },
            }
        ],
        "crossLine": {
            "yieldVariance": [{"assembly": "AsmA", "stddev": 0.5}],
            "falseCallVariance": [{"assembly": "AsmA", "stddev": 0.2}],
            "defectSimilarity": [
                {                    "pairs": [
                        {"lines": ["L1", "L2"], "similarity": 0.82},
                    ],
                }
            ],
        },
        "lineTrends": [
            {
                "line": "L1",
                "entries": [
                    {
                        "date": "2024-01-01",
                        "windowYield": 97.0,
                        "truePartYield": 96.5,
                        "rawPartYield": 95.0,
                        "boards": 40,
                        "parts": 600,
                        "ngParts": 12,
                        "falseCalls": 3,
                        "windows": 900,
                        "ngWindows": 6,
                        "windowsPerBoard": 22.5,
                        "defectsPerBoard": 0.15,
                    },
                    {
                        "date": "2024-01-02",
                        "windowYield": 97.5,
                        "truePartYield": 96.9,
                        "rawPartYield": 95.4,
                        "boards": 40,
                        "parts": 600,
                        "ngParts": 13,
                        "falseCalls": 2,
                        "windows": 900,
                        "ngWindows": 7,
                        "windowsPerBoard": 22.5,
                        "defectsPerBoard": 0.175,
                    },
                ],
            }
        ],
        "trendInsights": {
            "lineDrift": [
                {"line": "L1", "change": 1.5, "start": 96.0, "end": 97.5},
            ],
            "assemblyLearning": [
                {                    "line": "L1",
                    "start": ["2024-01-01", 95.0],
                    "end": ["2024-01-05", 97.5],
                    "change": 2.5,
                }
            ],
        },
        "benchmarking": {
            "lineVsCompany": [
                {
                    "line": "L1",
                    "windowYieldDelta": 1.0,
                    "falseCallDelta": -0.1,
                    "falseCallPpmDelta": -50.0,
                    "falseCallDpmDelta": -35.0,
                    "defectDpmDelta": -12.0,
                }
            ],
            "bestYield": {"line": "L1", "windowYield": 98.5},
            "lowestFalseCalls": {"line": "L1", "falseCallsPerBoard": 0.32},
            "mostConsistent": {"line": "L1", "stddev": 0.18},
        },
        "companyAverages": {
            "windowYield": 97.3,
            "truePartYield": 96.4,
            "rawPartYield": 95.1,
            "falseCallsPerBoard": 0.4,
            "falseCallPpm": 1400.0,
            "falseCallDpm": 900.0,
            "defectDpm": 600.0,
            "ngParts": 120.0,
            "ngWindows": 80.0,
            "windowsPerBoard": 15.0,
            "defectsPerBoard": 0.3,
        },
        "trendInsightsSummary": {},
    }


def _mock_line_report(monkeypatch):
    payload_template = _sample_line_payload()

    def _build_payload(start, end):
        assert start is None
        assert end is None
        return copy.deepcopy(payload_template)

    chart_data = base64.b64encode(b"chart").decode()
    charts = {
        "lineYieldOverlayImg": f"data:image/png;base64,{chart_data}",
        "lineFalseCallSmallMultiplesImg": f"data:image/png;base64,{chart_data}",
        "lineDefectSmallMultiplesImg": f"data:image/png;base64,{chart_data}",
        "linePpmDpmComparisonImg": f"data:image/png;base64,{chart_data}",
    }

    def _charts(payload):
        for metric in payload.get("lineMetrics", []):
            assert "rawPartYield" in metric
            assert "truePartYield" in metric
            assert "windowsPerBoard" in metric
            assert "defectsPerBoard" in metric
            assert "ngParts" in metric
            assert "ngWindows" in metric
        for trend in payload.get("lineTrends", []):
            for entry in trend.get("entries", []):
                assert "rawPartYield" in entry
                assert "truePartYield" in entry
                assert "windowsPerBoard" in entry
                assert "defectsPerBoard" in entry
                assert "boards" in entry
                assert "parts" in entry
        return charts.copy()

    monkeypatch.setattr(routes, "build_line_report_payload", _build_payload)
    monkeypatch.setattr(routes, "_generate_line_report_charts", _charts)
    monkeypatch.setattr(routes, "_load_report_css", lambda: "")
    monkeypatch.setattr(
        routes,
        "render_html_to_pdf",
        lambda html, base_url=None: b"%PDF-1.4 line report\n",
    )


@pytest.fixture
def app_instance(monkeypatch):
    monkeypatch.setattr(app_module, "create_client", lambda url, key: object())
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")
    app = create_app()
    return app


def test_line_report_api_returns_expected_metrics(app_instance, monkeypatch):
    grouped_rows = {
        "2024-07-01": {
            "L1": [
                {
                    "report_date": "2024-07-01",
                    "line": "L1",
                    "model_name": "AsmA",
                    "ppm_total_parts": 100,
                    "ppm_total_boards": 10,
                    "ppm_falsecall_parts": 5,
                    "ppm_ng_parts": 15,
                    "dpm_total_boards": 10,
                    "dpm_total_windows": 200,
                    "dpm_ng_windows": 10,
                    "dpm_falsecall_windows": 4,
                }
            ],
            "L2": [
                {
                    "report_date": "2024-07-01",
                    "line": "L2",
                    "model_name": "AsmA",
                    "ppm_total_parts": 80,
                    "ppm_total_boards": 8,
                    "ppm_falsecall_parts": 2,
                    "ppm_ng_parts": 6,
                    "dpm_total_boards": 8,
                    "dpm_total_windows": 80,
                    "dpm_ng_windows": 5,
                    "dpm_falsecall_windows": 1,
                }
            ],
        },
        "2024-07-02": {
            "L1": [
                {
                    "report_date": "2024-07-02",
                    "line": "L1",
                    "model_name": "AsmB",
                    "ppm_total_parts": 120,
                    "ppm_total_boards": 12,
                    "ppm_falsecall_parts": 3,
                    "ppm_ng_parts": 8,
                    "dpm_total_boards": 12,
                    "dpm_total_windows": 120,
                    "dpm_ng_windows": 6,
                    "dpm_falsecall_windows": 3,
                }
            ],
        },
        "2024-07-03": {
            "L3": [
                {
                    "report_date": "2024-07-03",
                    "line": "L3",
                    "model_name": "AsmC",
                    "ppm_total_parts": 50,
                    "ppm_total_boards": 5,
                    "ppm_falsecall_parts": 1,
                    "ppm_ng_parts": 4,
                    "dpm_total_boards": 5,
                    "dpm_total_windows": 0,
                    "dpm_ng_windows": 0,
                    "dpm_falsecall_windows": 0,
                }
            ]
        },
    }

    query_calls: list[tuple[str, dict[str, object] | None]] = []

    def _query(sql, params=None):
        query_calls.append((sql, params))
        return grouped_rows, None

    monkeypatch.setattr(routes, "query_aoi_base_daily", _query)

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        response = client.get(
            "/api/reports/line?start_date=2024-07-01&end_date=2024-07-05"
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert query_calls and "aoi_base_daily" in query_calls[0][0]
    assert query_calls[0][1] == {
        "start_date": "2024-07-01",
        "end_date": "2024-07-05",
    }
    assert payload["lineMetrics"]
    metrics = {item["line"]: item for item in payload["lineMetrics"]}
    assert pytest.approx(metrics["L1"]["windowYield"], rel=1e-3) == 95.0
    assert pytest.approx(metrics["L1"]["truePartYield"], rel=1e-3) == 93.181818
    assert pytest.approx(metrics["L1"]["rawPartYield"], rel=1e-3) == 89.545455
    assert pytest.approx(metrics["L1"]["falseCallsPerBoard"], rel=1e-3) == 0.3636
    assert pytest.approx(metrics["L1"]["falseCallPpm"], rel=1e-4) == 36363.6363
    assert pytest.approx(metrics["L1"]["falseCallDpm"], rel=1e-4) == 21875.0
    assert pytest.approx(metrics["L1"]["defectDpm"], rel=1e-4) == 50000.0
    assert metrics["L1"]["confirmedDefects"] == pytest.approx(15.0)
    assert metrics["L1"]["windowConfirmedDefects"] == pytest.approx(16.0)
    assert pytest.approx(metrics["L1"]["boardsPerDay"], rel=1e-3) == 11.0
    assert metrics["L1"]["totalWindows"] == pytest.approx(320.0)
    assert metrics["L1"]["ngParts"] == pytest.approx(23.0)
    assert metrics["L1"]["ngWindows"] == pytest.approx(16.0)
    assert pytest.approx(metrics["L1"]["windowsPerBoard"], rel=1e-4) == 14.5455
    assert pytest.approx(metrics["L1"]["defectsPerBoard"], rel=1e-4) == 0.7273

    assert metrics["L3"]["confirmedDefects"] == pytest.approx(3.0)
    assert metrics["L3"]["windowConfirmedDefects"] is None
    assert pytest.approx(metrics["L3"]["defectDpm"], rel=1e-4) == 60000.0
    assert metrics["L3"]["ngParts"] == pytest.approx(4.0)
    assert metrics["L3"]["ngWindows"] == pytest.approx(0.0)
    assert pytest.approx(metrics["L3"]["windowsPerBoard"], rel=1e-4) == 0.0
    assert pytest.approx(metrics["L3"]["defectsPerBoard"], rel=1e-4) == 0.0

    assert payload["assemblyComparisons"]
    asmA = next(item for item in payload["assemblyComparisons"] if item["assembly"] == "AsmA")
    assert asmA["lines"]["L2"]["windowYield"] == pytest.approx(93.75)
    assert payload["benchmarking"]["bestYield"]["line"] == "L1"

    averages = payload["companyAverages"]
    assert averages["windowYield"] == pytest.approx(94.75)
    assert averages["truePartYield"] == pytest.approx(93.714286)
    assert averages["rawPartYield"] == pytest.approx(90.571429)
    assert averages["defectDpm"] == pytest.approx(52500.0)
    assert averages["ngParts"] == pytest.approx(33.0)
    assert averages["ngWindows"] == pytest.approx(21.0)
    assert averages["windowsPerBoard"] == pytest.approx(11.428571)
    assert averages["defectsPerBoard"] == pytest.approx(0.6)

    l1_trend = next(item for item in payload["lineTrends"] if item["line"] == "L1")
    day1 = next(entry for entry in l1_trend["entries"] if entry["date"] == "2024-07-01")
    assert day1["boards"] == pytest.approx(10.0)
    assert day1["parts"] == pytest.approx(100.0)
    assert day1["ngParts"] == pytest.approx(15.0)
    assert day1["falseCalls"] == pytest.approx(5.0)
    assert day1["windows"] == pytest.approx(200.0)
    assert day1["ngWindows"] == pytest.approx(10.0)
    assert day1["windowsPerBoard"] == pytest.approx(20.0)
    assert day1["defectsPerBoard"] == pytest.approx(1.0)


def test_line_report_api_sanitizes_non_finite_numbers(app_instance, monkeypatch):
    grouped_rows = {
        "2024-07-01": {
            "L1": [
                {
                    "report_date": "2024-07-01",
                    "line": "L1",
                    "model_name": "AsmA",
                    "Total Parts": "NaN",
                    "Total Boards": "Infinity",
                    "FalseCall Parts": "-Inf",
                    "NG Parts": "nan",
                    "Total Windows": "Infinity",
                    "dpm_total_boards": "Infinity",
                    "dpm_total_windows": "-Infinity",
                    "dpm_ng_windows": "NaN",
                    "dpm_falsecall_windows": "+Infinity",
                },
                {
                    "report_date": "2024-07-01",
                    "line": "L1",
                    "model_name": "AsmA",
                    "Total Parts": 100,
                    "Total Boards": 10,
                    "FalseCall Parts": 2,
                    "NG Parts": 4,
                    "Total Windows": 200,
                    "dpm_total_boards": 10,
                    "dpm_total_windows": 200,
                    "dpm_ng_windows": 5,
                    "dpm_falsecall_windows": 3,
                },
            ]
        }
    }

    monkeypatch.setattr(
        routes, "query_aoi_base_daily", lambda *args, **kwargs: (grouped_rows, None)
    )

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        response = client.get("/api/reports/line")

    assert response.status_code == 200
    payload = response.get_json()

    metrics = payload.get("lineMetrics", [])
    assert metrics
    for metric in metrics:
        for value in metric.values():
            if isinstance(value, (int, float)):
                assert math.isfinite(value)

    averages = payload.get("companyAverages", {})
    for value in averages.values():
        if isinstance(value, (int, float)):
            assert math.isfinite(value)

def test_build_line_report_payload_uses_windows_per_board_fallback(monkeypatch):
    grouped_rows = {
        "2024-08-01": {
            "L1": [
                {
                    "report_date": "2024-08-01",
                    "line": "L1",
                    "model_name": "AsmX",
                    "ppm_total_parts": 100,
                    "ppm_total_boards": 5,
                    "ppm_falsecall_parts": 3,
                    "ppm_ng_parts": 7,
                    "dpm_total_boards": 5,
                    "Windows per board": 40,
                    "dpm_ng_windows": 4,
                    "dpm_falsecall_windows": 1,
                }
            ],
            "L2": [
                {
                    "report_date": "2024-08-01",
                    "line": "L2",
                    "model_name": "AsmX",
                    "ppm_total_parts": 80,
                    "ppm_total_boards": 4,
                    "ppm_falsecall_parts": 1,
                    "ppm_ng_parts": 3,
                    "dpm_total_boards": 4,
                    "dpm_total_windows": 160,
                    "dpm_ng_windows": 6,
                    "dpm_falsecall_windows": 2,
                }
            ],
        }
    }

    monkeypatch.setattr(
        routes, "query_aoi_base_daily", lambda *args, **kwargs: (grouped_rows, None)
    )

    payload = routes.build_line_report_payload()

    metrics = {item["line"]: item for item in payload["lineMetrics"]}
    l1 = metrics["L1"]
    assert l1["totalWindows"] == pytest.approx(200.0)
    assert l1["windowYield"] == pytest.approx(98.0)
    assert l1["defectsPerBoard"] == pytest.approx(0.8)
    assert l1["defectDpm"] == pytest.approx(20000.0)
    assert l1["windowsPerBoard"] == pytest.approx(40.0)

    trend = next(item for item in payload["lineTrends"] if item["line"] == "L1")
    day = next(entry for entry in trend["entries"] if entry["date"] == "2024-08-01")
    assert day["windows"] == pytest.approx(200.0)
    assert day["windowsPerBoard"] == pytest.approx(40.0)
    assert day["defectsPerBoard"] == pytest.approx(0.8)

    asm = next(
        item for item in payload["assemblyComparisons"] if item["assembly"] == "AsmX"
    )
    l1_assembly = asm["lines"]["L1"]
    assert l1_assembly["windows"] == pytest.approx(200.0)
    assert l1_assembly["defectsPerBoard"] == pytest.approx(0.8)


def test_build_line_report_payload_handles_multi_month_range(monkeypatch):
    start = date(2024, 1, 1)
    end = date(2024, 3, 31)

    grouped_rows = {
        "2024-01-15": {
            "L1": [
                {
                    "report_date": "2024-01-15",
                    "line": "L1",
                    "model_name": "AsmA",
                    "ppm_total_parts": 100,
                    "ppm_total_boards": 10,
                    "ppm_falsecall_parts": 5,
                    "ppm_ng_parts": 10,
                    "dpm_total_boards": 10,
                    "dpm_total_windows": 200,
                    "dpm_ng_windows": 10,
                    "dpm_falsecall_windows": 4,
                }
            ],
        },
        "2024-02-15": {
            "L1": [
                {
                    "report_date": "2024-02-15",
                    "line": "L1",
                    "model_name": "AsmA",
                    "ppm_total_parts": 90,
                    "ppm_total_boards": 9,
                    "ppm_falsecall_parts": 4,
                    "ppm_ng_parts": 9,
                    "dpm_total_boards": 9,
                    "dpm_total_windows": 180,
                    "dpm_ng_windows": 9,
                    "dpm_falsecall_windows": 3,
                }
            ],
        },
        "2024-03-15": {
            "L1": [
                {
                    "report_date": "2024-03-15",
                    "line": "L1",
                    "model_name": "AsmA",
                    "ppm_total_parts": 110,
                    "ppm_total_boards": 11,
                    "ppm_falsecall_parts": 6,
                    "ppm_ng_parts": 11,
                    "dpm_total_boards": 11,
                    "dpm_total_windows": 220,
                    "dpm_ng_windows": 11,
                    "dpm_falsecall_windows": 5,
                }
            ],
        },
        "2024-04-01": {
            "L1": [
                {
                    "report_date": "2024-04-01",
                    "line": "L1",
                    "model_name": "AsmA",
                    "ppm_total_parts": 120,
                    "ppm_total_boards": 12,
                    "ppm_falsecall_parts": 7,
                    "ppm_ng_parts": 12,
                    "dpm_total_boards": 12,
                    "dpm_total_windows": 240,
                    "dpm_ng_windows": 12,
                    "dpm_falsecall_windows": 6,
                }
            ],
        },
    }

    query_calls: list[tuple[str, dict[str, object] | None]] = []

    def _query(sql, params=None):
        query_calls.append((sql, params))
        return grouped_rows, None

    monkeypatch.setattr(routes, "query_aoi_base_daily", _query)

    payload = routes.build_line_report_payload(start, end)

    assert len(query_calls) == 1
    assert "aoi_base_daily" in query_calls[0][0]
    assert query_calls[0][1] == {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }

    metrics = {item["line"]: item for item in payload["lineMetrics"]}
    l1_metrics = metrics["L1"]
    assert l1_metrics["totalParts"] == pytest.approx(300.0)
    assert l1_metrics["totalBoards"] == pytest.approx(30.0)
    assert l1_metrics["ngParts"] == pytest.approx(30.0)

    trends = next(item for item in payload["lineTrends"] if item["line"] == "L1")
    trend_dates = {entry["date"] for entry in trends["entries"]}
    assert trend_dates == {"2024-01-15", "2024-02-15", "2024-03-15"}
    assert "2024-04-01" not in trend_dates


def test_line_report_export_html_includes_charts(app_instance, monkeypatch):
    _mock_line_report(monkeypatch)

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/line/export?format=html")

    assert resp.status_code == 200
    disposition = resp.headers.get("Content-Disposition", "")
    assert "__line_report.html" in disposition
    html = resp.data.decode()
    assert "data:image/png;base64" in html
    assert "Benchmarking KPIs" in html
    assert "L1" in html


def test_line_report_export_pdf_succeeds(app_instance, monkeypatch):
    _mock_line_report(monkeypatch)

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/line/export?format=pdf")

    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF-1.4")


def test_line_report_export_handles_pdf_error(app_instance, monkeypatch):
    monkeypatch.setattr(routes, "build_line_report_payload", lambda start, end: {
        "lineMetrics": [],
        "assemblyComparisons": [],
        "crossLine": {},
        "lineTrends": [],
        "trendInsights": {},
        "benchmarking": {"lineVsCompany": []},
        "companyAverages": {
            "windowYield": 0,
            "truePartYield": 0,
            "rawPartYield": 0,
            "falseCallsPerBoard": 0,
            "falseCallPpm": 0,
            "falseCallDpm": 0,
            "defectDpm": 0,
        },
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


def test_line_report_export_rejects_unknown_format(app_instance, monkeypatch):
    monkeypatch.setattr(routes, "build_line_report_payload", lambda start, end: {})
    monkeypatch.setattr(routes, "_generate_line_report_charts", lambda payload: {})
    monkeypatch.setattr(routes, "render_template", lambda template, **context: "<html></html>")

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/line/export?format=xlsx")

    assert resp.status_code == 400
    assert resp.get_json() == {"message": "Unsupported format. Choose pdf or html."}
