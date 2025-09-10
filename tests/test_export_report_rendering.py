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
            "<section class='report-section cover-page'>cover"
            "{% if show_summary %}"
            "<div class='summary'>"
            "{% for k in summary_kpis %}<div class='kpi'>{{ k.label }}</div>{% endfor %}"
            "</div>"
            "<div class='toc'>Table of Contents</div>"
            "{% endif %}"
            "</section>"
            "{% elif show_summary %}"
            "<section class='report-section summary-page'>"
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
        assert "KPI1" in html
        assert "JobA" in html
        assert "Program Review Queue" not in html


def test_cover_contains_summary_when_enabled(app_instance, monkeypatch):
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
        assert "<div class='summary'>" in cover_content
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
        assert "Table of Contents" in cover_content
        assert cover_content.index("<div class='summary'>") < cover_content.index("Table of Contents")


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
