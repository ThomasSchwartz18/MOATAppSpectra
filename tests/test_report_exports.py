import os
import sys
import pytest

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module
from app import create_app
from app.main import routes
from app.main.pdf_utils import PdfGenerationError


@pytest.fixture
def app_instance(monkeypatch):
    monkeypatch.setattr(app_module, "create_client", lambda url, key: object())
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")
    app = create_app()
    return app


def _mock_integrated_report(monkeypatch):
    monkeypatch.setattr(routes, "build_report_payload", lambda start, end: {})
    monkeypatch.setattr(routes, "_generate_report_charts", lambda payload: {})
    monkeypatch.setattr(routes, "render_template", lambda template, **context: "<html></html>")


def test_integrated_export_returns_dependency_error(app_instance, monkeypatch):
    _mock_integrated_report(monkeypatch)
    message = "Install Pango, GObject, and Cairo"

    def _raise_pdf_error(*args, **kwargs):
        raise PdfGenerationError(message)

    monkeypatch.setattr(routes, "render_html_to_pdf", _raise_pdf_error)

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        response = client.get("/reports/integrated/export?format=pdf")

    assert response.status_code == 503
    payload = response.get_json()
    assert payload == {"message": message}
