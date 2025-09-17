import os
import io
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


def test_upload_fi_reports_missing_header(app_instance):
    client = app_instance.test_client()
    csv_content = (
        "Date,Shift,Operator,Customer,Assembly,Rev,Quantity Inspected,Quantity Rejected,Additional Information\n"
        "07/01/2024,1,Alice,ACME,A1,R1,10,1,Info\n"
    )
    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "fi.csv")}
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "ADMIN"
        resp = client.post("/fi_reports/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "Missing columns: Job Number" in body
    assert "Unexpected columns: none" in body


def test_upload_fi_reports_headers_with_spaces(app_instance, monkeypatch):
    client = app_instance.test_client()
    captured = []

    def fake_insert(row):
        captured.append(row)
        return {}, None

    monkeypatch.setattr(routes, "insert_fi_report", fake_insert)
    csv_content = (
        " Date ,Shift ,Operator ,Customer ,Assembly ,Rev ,Job Number ,Quantity Inspected ,Quantity Rejected ,Additional Information \n"
        "07/01/2024,1,Alice,ACME,A1,R1,J1,10,1,Info\n"
    )
    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "fi.csv")}
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "ADMIN"
        resp = client.post("/fi_reports/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.get_json()["inserted"] == 1
    assert captured[0]["Date"] == "07/01/2024"
    assert captured[0]["Quantity Inspected"] == "10"
