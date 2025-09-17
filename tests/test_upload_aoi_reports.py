import os
import io
from datetime import date
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


def test_upload_aoi_with_program_column(app_instance, monkeypatch):
    client = app_instance.test_client()
    captured = {}

    def fake_insert(rows):
        captured["rows"] = rows
        return None, None

    monkeypatch.setattr(routes, "insert_aoi_reports_bulk", fake_insert)
    csv_content = (
        "Date,Shift,Operator,Customer,Program,Assembly,Rev,Job Number,Quantity Inspected,Quantity Rejected,Additional Information\n"
        "2024-07-01,1,Alice,ACME,Alpha,A1,R1,J1,10,1,Info\n"
    )
    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "aoi.csv")}
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "ADMIN"
        resp = client.post("/aoi_reports/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.get_json()["inserted"] == 1
    assert captured["rows"][0]["Program"] == "Alpha"


def test_upload_and_payload_builder_with_program(app_instance, monkeypatch):
    client = app_instance.test_client()
    captured = {}

    def fake_insert(rows):
        captured["rows"] = rows
        return None, None

    monkeypatch.setattr(routes, "insert_aoi_reports_bulk", fake_insert)
    csv_content = (
        "Date,Shift,Operator,Customer,Program,Assembly,Rev,Job Number,Quantity Inspected,Quantity Rejected,Additional Information\n"
        "2024-07-01,1,Alice,ACME,Alpha,A1,R1,J1,10,1,Info\n"
    )
    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "aoi.csv")}
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "ADMIN"
        resp = client.post("/aoi_reports/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 201
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (captured["rows"], None))
        monkeypatch.setattr(routes, "fetch_fi_reports", lambda: ([], None))
        payload = routes.build_aoi_daily_report_payload(date.fromisoformat("2024-07-01"))
    assert payload["shift1"][0]["program"] == "Alpha"


def test_upload_aoi_reports_reordered_headers(app_instance):
    client = app_instance.test_client()
    csv_content = (
        "Shift,Date,Operator,Customer,Program,Assembly,Rev,Job Number,Quantity Inspected,Quantity Rejected,Additional Information\n"
        "1,07/01/2024,Alice,ACME,Alpha,A1,R1,J1,10,1,Info\n"
    )
    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "aoi.csv")}
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "ADMIN"
        resp = client.post("/aoi_reports/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "Missing columns: none" in body
    assert "Columns out of order: Shift, Date" in body
    assert "Column order should be:" in body


def test_upload_aoi_reports_missing_header(app_instance):
    client = app_instance.test_client()
    csv_content = (
        "Date,Shift,Operator,Customer,Program,Assembly,Rev,Quantity Inspected,Quantity Rejected,Additional Information\n"
        "07/01/2024,1,Alice,ACME,Alpha,A1,R1,10,1,Info\n"
    )
    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "aoi.csv")}
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "ADMIN"
        resp = client.post("/aoi_reports/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "Missing columns: Job Number" in body
    assert "Unexpected columns: none" in body


def test_upload_aoi_reports_headers_with_spaces(app_instance, monkeypatch):
    client = app_instance.test_client()
    captured = {}

    def fake_insert(rows):
        captured["rows"] = rows
        return None, None

    monkeypatch.setattr(routes, "insert_aoi_reports_bulk", fake_insert)
    csv_content = (
        " Date ,Shift ,Operator ,Customer ,Program ,Assembly ,Rev ,Job Number ,Quantity Inspected ,Quantity Rejected ,Additional Information \n"
        "07/01/2024,1,Alice,ACME,Alpha,A1,R1,J1,10,1,Info\n"
    )
    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "aoi.csv")}
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "ADMIN"
        resp = client.post("/aoi_reports/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.get_json()["inserted"] == 1
    assert captured["rows"][0]["Date"] == "2024-07-01"
    assert captured["rows"][0]["Quantity Rejected"] == "1"


def test_upload_aoi_reports_missing_required_data(app_instance):
    client = app_instance.test_client()
    csv_content = (
        "Date,Shift,Operator,Customer,Program,Assembly,Rev,Job Number,Quantity Inspected,Quantity Rejected,Additional Information\n"
        "07/01/2024,1,Alice,ACME,Alpha,A1,R1,J1,10,1,\n"
        "07/01/2024,1,,ACME,Alpha,A1,R1,J2,5,0,\n"
        ",,,,,,,,,,\n"
    )
    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "aoi.csv")}
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "ADMIN"
        resp = client.post("/aoi_reports/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "Missing required data in rows - Row 3: Operator" in body


def test_upload_aoi_reports_ignores_blank_rows(app_instance, monkeypatch):
    client = app_instance.test_client()
    captured = {}

    def fake_insert(rows):
        captured["rows"] = rows
        return None, None

    monkeypatch.setattr(routes, "insert_aoi_reports_bulk", fake_insert)
    csv_content = (
        "Date,Shift,Operator,Customer,Program,Assembly,Rev,Job Number,Quantity Inspected,Quantity Rejected,Additional Information\n"
        "07/01/2024,1,Alice,ACME,Alpha,A1,R1,J1,10,1,\n"
        ",,,,,,,,,,\n"
    )
    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "aoi.csv")}
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "ADMIN"
        resp = client.post("/aoi_reports/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.get_json()["inserted"] == 1
    assert captured["rows"][0]["Operator"] == "Alice"
