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
        "lines": [{"label": "LineA", "value": 5}],
    }
    monkeypatch.setattr(
        routes, "build_line_report_payload", lambda start, end: sample_payload
    )
    monkeypatch.setattr(routes, "_generate_line_report_charts", lambda payload: {})

    def fake_render(template, **context):
        assert template == "report/line/index.html"
        tpl = (
            "{% if show_cover %}"
            "<section class='report-section cover-page'>cover</section>"
            "{% endif %}"
            "<div class='content'>Line Report</div>"
        )
        return render_template_string(tpl, **context)

    monkeypatch.setattr(routes, "render_template", fake_render)


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
        resp = client.get("/reports/line/export?format=html")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "cover-page" in html


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
