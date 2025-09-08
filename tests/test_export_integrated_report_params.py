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


def test_export_integrated_report_accepts_custom_fields(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        monkeypatch.setattr(routes, "build_report_payload", lambda start, end: {})
        monkeypatch.setattr(routes, "_generate_report_charts", lambda payload: {})
        captured = {}

        def fake_render(template, **context):
            captured.update(context)
            return "ok"

        monkeypatch.setattr(routes, "render_template", fake_render)
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        payload = {
            "show_cover": False,
            "title": "My Title",
            "subtitle": "Sub",
            "report_date": "2024-09-01",
            "period": "Q3",
            "author": "Alice",
            "logo_url": "http://logo",
            "footer_left": "left foot",
        }
        resp = client.get("/reports/integrated/export?show_summary=0", json=payload)
        assert resp.status_code == 200
        assert captured["show_cover"] is False
        assert captured["show_summary"] is False
        assert captured["title"] == "My Title"
        assert captured["subtitle"] == "Sub"
        assert captured["report_date"] == "2024-09-01"
        assert captured["period"] == "Q3"
        assert captured["author"] == "Alice"
        assert captured["logo_url"] == "http://logo"
        assert captured["footer_left"] == "left foot"
