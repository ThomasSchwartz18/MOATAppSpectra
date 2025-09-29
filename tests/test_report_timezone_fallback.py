import os
import sys

import pytest
from zoneinfo import ZoneInfoNotFoundError

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


def test_export_endpoints_fallback_to_utc(monkeypatch, app_instance):
    def _raise_zoneinfo(name):
        raise ZoneInfoNotFoundError()

    monkeypatch.setattr(routes, "ZoneInfo", _raise_zoneinfo)

    monkeypatch.setattr(routes, "_load_report_css", lambda: "")
    monkeypatch.setattr(routes, "build_line_report_payload", lambda start, end: {})
    monkeypatch.setattr(routes, "_generate_line_report_charts", lambda payload: {})
    monkeypatch.setattr(routes, "build_report_payload", lambda start, end: {})
    monkeypatch.setattr(routes, "_generate_report_charts", lambda payload: {})
    monkeypatch.setattr(routes, "build_aoi_daily_report_payload", lambda day, operator, assembly: {})
    monkeypatch.setattr(routes, "_generate_aoi_daily_report_charts", lambda payload: {})
    monkeypatch.setattr(routes, "build_operator_report_payload", lambda start, end, operator: {})
    monkeypatch.setattr(routes, "_generate_operator_report_charts", lambda payload: {})
    monkeypatch.setattr(routes, "fetch_combined_reports", lambda: ([], None))

    def fake_render(template, **context):
        return f"<html>{context.get('generated_at', '')}</html>"

    monkeypatch.setattr(routes, "render_template", fake_render)

    client = app_instance.test_client()

    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"

        responses = [
            client.get("/reports/line/export?format=html"),
            client.get("/reports/integrated/export?format=html"),
            client.get(
                "/reports/aoi_daily/export?format=html&date=2023-01-01",
            ),
            client.get("/reports/operator/export?format=html"),
        ]

    for response in responses:
        assert response.status_code == 200
        assert "UTC" in response.data.decode()

