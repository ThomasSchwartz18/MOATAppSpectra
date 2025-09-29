import os
import io
import sys
import pytest
from flask import render_template_string

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
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


def _mock_report(monkeypatch):
    sample_payload = {
        "summary_kpis": [{"label": "KPI1", "value": 1}],
        "jobs": [{"label": "JobA", "value": 10}],
        "avgBoards": 10,
    }
    monkeypatch.setattr(routes, "build_report_payload", lambda start, end: sample_payload)
    monkeypatch.setattr(routes, "_generate_report_charts", lambda payload: {})

    def fake_render(template, **context):
        tpl = (
            "{% if show_cover %}"
            "<section class='report-section cover-page'>"
            "{% if logo_url %}<img class='logo' src='{{ logo_url }}'/>{% endif %}"
            "cover</section>"
            "{% endif %}"
            "{% if show_summary %}"
            "<section class='report-section summary-page{% if show_cover %} summary-after-cover{% endif %}'>"
            "<div class='summary'>"
            "{% for k in summary_kpis %}<div class='kpi'>{{ k.label }}</div>{% endfor %}"
            "</div>"
            "<div class='toc'>Table of Contents</div>"
            "</section>"
            "{% endif %}"
            "{% for job in jobs %}<div class='job'>{{ job.label }}</div>{% endfor %}"
        )
        return render_template_string(tpl, **context)

    monkeypatch.setattr(routes, "render_template", fake_render)


def _mock_line_report(monkeypatch):
    sample_payload = {
        "lineMetrics": [
            {
                "line": "Line A",
                "windowYield": 98.2,
                "truePartYield": 97.5,
                "rawPartYield": 96.0,
                "confirmedDefects": 10,
                "ngParts": 15,
                "ngWindows": 20,
                "falseCallsPerBoard": 0.3,
                "windowsPerBoard": 12.0,
                "defectsPerBoard": 0.1,
                "falseCallPpm": 120.0,
                "falseCallDpm": 85.0,
                "defectDpm": 65.0,
                "boardsPerDay": 100.0,
                "totalWindows": 1500.0,
                "totalParts": 8000.0,
                "totalBoards": 400.0,
            },
            {
                "line": "Line B",
                "windowYield": 94.0,
                "truePartYield": 92.1,
                "rawPartYield": 91.5,
                "confirmedDefects": 30,
                "ngParts": 45,
                "ngWindows": 55,
                "falseCallsPerBoard": 0.4,
                "windowsPerBoard": 10.0,
                "defectsPerBoard": 0.2,
                "falseCallPpm": 150.0,
                "falseCallDpm": 110.0,
                "defectDpm": 90.0,
                "boardsPerDay": 80.0,
                "totalWindows": 1000.0,
                "totalParts": 6000.0,
                "totalBoards": 300.0,
            },
        ],
        "benchmarking": {
            "bestYield": {
                "line": "Line A",
                "windowYield": 98.2,
                "truePartYield": 97.5,
                "rawPartYield": 96.0,
                "falseCallsPerBoard": 0.3,
            },
            "lowestFalseCalls": {
                "line": "Line B",
                "falseCallsPerBoard": 0.2,
            },
            "mostConsistent": None,
            "lineVsCompany": [],
        },
        "companyAverages": {
            "windowYield": 96.0,
            "truePartYield": 95.0,
            "rawPartYield": 94.5,
            "falseCallsPerBoard": 0.35,
            "falseCallPpm": 140.0,
            "falseCallDpm": 100.0,
            "defectDpm": 80.0,
            "ngParts": 60.0,
            "ngWindows": 75.0,
            "windowsPerBoard": 11.0,
            "defectsPerBoard": 0.15,
        },
        "trendInsights": {"lineDrift": [], "assemblyLearning": []},
        "lineYieldImg": "",
        "lineFalseCallImg": "",
        "linePpmImg": "",
        "lineTrendImg": "",
        "lineTrends": [],
        "assemblyComparisons": [],
        "crossLine": {
            "yieldVariance": [],
            "falseCallVariance": [],
            "defectSimilarity": [],
        },
        "linePeriodSummary": {
            "lines": [
                {
                    "line": "Line A",
                    "true_part_yield_pct": 97.5,
                    "window_yield_pct": 98.2,
                    "raw_part_yield_pct": 96.0,
                    "fc_per_board": 0.3,
                    "defects_per_board": 0.1,
                    "total_boards": 400.0,
                    "total_parts": 8000.0,
                    "total_windows": 1500.0,
                    "false_calls": 120.0,
                    "ng_windows": 40.0,
                },
                {
                    "line": "Line B",
                    "true_part_yield_pct": 92.1,
                    "window_yield_pct": 94.0,
                    "raw_part_yield_pct": 91.5,
                    "fc_per_board": 0.4,
                    "defects_per_board": 0.2,
                    "total_boards": 300.0,
                    "total_parts": 6000.0,
                    "total_windows": 1000.0,
                    "false_calls": 120.0,
                    "ng_windows": 60.0,
                },
            ],
            "focus": {
                "line": "Line A",
                "true_part_yield_pct": 97.5,
                "window_yield_pct": 98.2,
                "raw_part_yield_pct": 96.0,
                "fc_per_board": 0.3,
                "defects_per_board": 0.1,
                "total_boards": 400.0,
                "total_parts": 8000.0,
                "total_windows": 1500.0,
                "false_calls": 120.0,
                "ng_windows": 40.0,
            },
            "best": {
                "line": "Line A",
                "true_part_yield_pct": 97.5,
                "window_yield_pct": 98.2,
                "raw_part_yield_pct": 96.0,
            },
            "worst": {
                "line": "Line B",
                "true_part_yield_pct": 92.1,
                "window_yield_pct": 94.0,
                "raw_part_yield_pct": 91.5,
            },
            "overall": {
                "line": "All Lines",
                "true_part_yield_pct": 95.0,
                "window_yield_pct": 96.0,
                "raw_part_yield_pct": 94.5,
                "fc_per_board": 0.3,
                "defects_per_board": 0.1,
                "total_boards": 700.0,
                "total_parts": 14000.0,
                "total_windows": 2500.0,
                "false_calls": 210.0,
                "ng_windows": 100.0,
            },
        },
    }
    monkeypatch.setattr(
        routes, "build_line_report_payload", lambda start, end: sample_payload
    )
    monkeypatch.setattr(routes, "_generate_line_report_charts", lambda payload: {})


def _mock_operator_report(monkeypatch):
    sample_payload = {
        "summary": {"avg": 1},
        "operators": [{"name": "OpA"}],
    }
    monkeypatch.setattr(
        routes,
        "build_operator_report_payload",
        lambda start, end, operator=None: sample_payload,
    )
    monkeypatch.setattr(routes, "_generate_operator_report_charts", lambda payload: {})
    monkeypatch.setattr(routes, "fetch_combined_reports", lambda: ({}, None))

    def fake_render(template, **context):
        assert template == "report/operator/index.html"
        tpl = (
            "{% if show_cover %}"
            "<section class='report-section cover-page'>cover</section>"
            "{% endif %}"
            "<div class='content'>Operator Report</div>"
        )
        return render_template_string(tpl, **context)

    monkeypatch.setattr(routes, "render_template", fake_render)


def _mock_aoi_daily_report(monkeypatch):
    sample_payload = {
        "rows": [{"assembly": "A1", "value": 1}],
    }
    monkeypatch.setattr(
        routes,
        "build_aoi_daily_report_payload",
        lambda day, operator, assembly: sample_payload,
    )
    monkeypatch.setattr(routes, "_generate_aoi_daily_report_charts", lambda payload: {})

    def fake_render(template, **context):
        assert template == "report/aoi_daily/index.html"
        tpl = (
            "{% if show_cover %}"
            "<section class='report-section cover-page'>cover</section>"
            "{% endif %}"
            "<div class='content'>AOI Daily Report</div>"
        )
        return render_template_string(tpl, **context)

    monkeypatch.setattr(routes, "render_template", fake_render)


def test_show_cover_false_and_summary_one_page(app_instance, monkeypatch):
    _mock_report(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/integrated/export?format=html",
            json={"show_cover": False, "show_summary": True},
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "cover-page" not in html
        assert html.count("<div class='summary'>") == 1
        assert "Table of Contents" in html
        assert "summary-after-cover" not in html
        assert "KPI1" in html
        assert "JobA" in html
        assert "Program Review Queue" not in html


def test_integrated_export_defaults_include_cover(app_instance, monkeypatch):
    _mock_report(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/integrated/export?format=html")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "cover-page" in html


def test_line_export_defaults_include_cover(app_instance, monkeypatch):
    _mock_line_report(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/line/export?format=html&start_date=2024-01-01&end_date=2024-01-31"
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "cover-page" in html
        assert (
            "Between 2024-01-01 and 2024-01-31, Line A inspected 400 boards with a true part"
            " yield of 97.50% and a window yield of 98.20%."
        ) in html
        assert "Average false calls per board: 0.30; defects per board: 0.10." in html
        assert "<strong>Best yield:</strong> Line A at 97.50%" in html
        assert "<strong>Needs attention:</strong> Line B at 92.10%" in html


def test_operator_export_defaults_include_cover(app_instance, monkeypatch):
    _mock_operator_report(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/operator/export?format=html")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "cover-page" in html


def test_aoi_daily_export_defaults_include_cover(app_instance, monkeypatch):
    _mock_aoi_daily_report(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/aoi_daily/export?format=html&date=2024-01-01")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "cover-page" in html


def test_cover_excludes_summary_when_enabled(app_instance, monkeypatch):
    _mock_report(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/integrated/export?format=html",
            json={"show_cover": True, "show_summary": True},
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "cover-page" in html
        start = html.index("cover-page")
        end = html.index("</section>", start)
        cover_content = html[start:end]
        assert "<div class='summary'>" not in cover_content
        assert "summary-after-cover" in html
        summary_start = html.index("summary-page", end)
        summary_end = html.index("</section>", summary_start)
        summary_content = html[summary_start:summary_end]
        assert "<div class='summary'>" in summary_content
        assert "KPI1" in html
        assert "JobA" in html
        assert "Program Review Queue" not in html


def test_cover_contains_toc_when_summary_enabled(app_instance, monkeypatch):
    _mock_report(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/integrated/export?format=html",
            json={"show_cover": True, "show_summary": True},
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        start = html.index("cover-page")
        end = html.index("</section>", start)
        cover_content = html[start:end]
        assert "Table of Contents" not in cover_content
        summary_start = html.index("summary-page", end)
        summary_end = html.index("</section>", summary_start)
        summary_content = html[summary_start:summary_end]
        assert "<div class='summary'>" in summary_content
        assert "Table of Contents" in summary_content
        assert summary_content.index("<div class='summary'>") < summary_content.index("Table of Contents")


def test_integrated_export_uses_absolute_logo_url(app_instance, monkeypatch):
    _mock_report(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/integrated/export?format=html",
            json={"show_cover": True, "show_summary": False},
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "http://localhost/static/images/company-logo.png" in html


def test_data_keys_present_in_pdf(app_instance, monkeypatch):
    _mock_report(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/integrated/export?format=pdf",
            json={"show_cover": False, "show_summary": True},
        )
        assert resp.status_code == 200
        pdfminer = pytest.importorskip("pdfminer.high_level")
        from pdfminer.high_level import extract_text

        pdf_text = extract_text(io.BytesIO(resp.data))
        assert "KPI1" in pdf_text
        assert "JobA" in pdf_text
