import os
import sys
from datetime import date

import pytest
from werkzeug.exceptions import InternalServerError

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app as app_module  # noqa: E402
from app import create_app  # noqa: E402
from app.main import routes  # noqa: E402
from app.main.pdf_utils import PdfGenerationError  # noqa: E402


@pytest.fixture
def app_instance(monkeypatch):
    monkeypatch.setattr(app_module, "create_client", lambda url, key: object())
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")
    return create_app()


def _login(client, role=None):
    with client.session_transaction() as session:
        session["username"] = "tester"
        if role:
            session["role"] = role


def _sample_part_rows():
    return [
        {
            "inspection_date": "2024-01-01",
            "part_number": "PN-1",
            "assembly": "ASM-A",
            "line": "L1",
            "program": "ProgramA",
            "component_family": "BGA",
            "defect_code": "BRG",
            "defect_type": "Solder",
            "operator": "Alice",
            "operator_disposition": "False Call",
            "operator_confirmation": "",
            "offset_x": 0.12,
            "offset_y": -0.05,
            "offset_theta": 0.3,
            "height": 0.15,
            "defect_density": 1.2,
            "false_call": True,
            "board_serial": "B1",
        },
        {
            "inspection_date": "2024-01-01",
            "part_number": "PN-2",
            "assembly": "ASM-A",
            "line": "L1",
            "program": "ProgramA",
            "component_family": "BGA",
            "defect_code": "MST",
            "defect_type": "Placement",
            "operator": "Bob",
            "operator_disposition": "Confirmed",
            "operator_confirmation": "confirmed",
            "offset_x": -0.08,
            "offset_y": 0.02,
            "offset_theta": 0.1,
            "height": 0.18,
            "defect_density": 1.0,
            "false_call": False,
            "board_serial": "B2",
        },
        {
            "inspection_date": "2024-01-02",
            "part_number": "PN-1",
            "assembly": "ASM-B",
            "line": "L2",
            "program": "ProgramB",
            "component_family": "Connector",
            "defect_code": "BRG",
            "defect_type": "Solder",
            "operator": "Alice",
            "operator_disposition": "Confirmed",
            "operator_confirmation": "confirmed",
            "offset_x": 0.05,
            "offset_y": 0.01,
            "offset_theta": 0.2,
            "height": 0.22,
            "defect_density": 0.8,
            "false_call": False,
            "board_serial": "B3",
        },
    ]


def test_build_part_report_payload_computes_metrics(app_instance, monkeypatch):
    rows = _sample_part_rows()
    captured = {}

    def _fake_fetch(start_date=None, end_date=None, page_size=None):
        captured["start"] = start_date
        captured["end"] = end_date
        captured["page_size"] = page_size
        return rows, None

    monkeypatch.setattr(routes, "fetch_part_results", _fake_fetch)

    with app_instance.app_context():
        payload = routes.build_part_report_payload(date(2024, 1, 1), date(2024, 1, 2))

    assert captured == {"start": date(2024, 1, 1), "end": date(2024, 1, 2), "page_size": 1000}
    assert payload["meta"]["totalRecords"] == 3
    assert payload["meta"]["totalFalseCalls"] == 1
    assert payload["defectDistributions"]["byDefectCode"][0]["label"] == "BRG"
    assert payload["falseCallPatterns"]["byPartNumber"][0]["label"] == "PN-1"
    assert payload["yieldReliability"]["defectsPerBoard"] == pytest.approx(1.0)
    assert payload["spatialMetrics"]["offsets"]["meanX"] == pytest.approx((0.12 - 0.08 + 0.05) / 3)
    alice = payload["operatorLinkages"]["byOperator"][0]
    assert alice["operator"] == "Alice"
    assert alice["falseCallRate"] == pytest.approx(0.5)
    assert payload["timeSeries"]["daily"][0]["defects"] == 2.0
    assert payload["insights"]["highlights"]


def test_build_part_report_payload_raises_on_error(app_instance, monkeypatch):
    monkeypatch.setattr(routes, "fetch_part_results", lambda **kwargs: (None, "boom"))
    with app_instance.app_context():
        with pytest.raises(InternalServerError):
            routes.build_part_report_payload()


def test_part_report_api_requires_login(app_instance):
    client = app_instance.test_client()
    resp = client.get("/api/reports/part")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


def test_part_report_api_returns_payload(app_instance, monkeypatch):
    client = app_instance.test_client()

    def _build(start, end):
        assert start is None
        assert end is None
        return {"meta": {"totalRecords": 0}}

    monkeypatch.setattr(routes, "build_part_report_payload", _build)
    with app_instance.app_context():
        _login(client)
        resp = client.get("/api/reports/part")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["meta"]["totalRecords"] == 0
    assert data["start"] == ""
    assert data["end"] == ""


def test_part_report_page_renders(app_instance):
    client = app_instance.test_client()
    with app_instance.app_context():
        _login(client)
        resp = client.get("/reports/part")
    assert resp.status_code == 200
    assert b"Part Report" in resp.data


def test_part_report_export_handles_pdf_error(app_instance, monkeypatch):
    client = app_instance.test_client()
    sample_payload = {
        "meta": {
            "totalRecords": 0,
            "totalFalseCalls": 0,
            "dateRange": [None, None],
            "uniquePartNumbers": 0,
            "uniqueAssemblies": 0,
            "uniquePrograms": 0,
            "uniqueLines": 0,
            "uniqueOperators": 0,
            "totalBoards": 0,
        },
        "defectDistributions": {
            "byDefectCode": [],
            "byComponentFamily": [],
            "byAssembly": [],
            "byLine": [],
            "byProgram": [],
        },
        "spatialMetrics": {
            "offsets": {"meanX": 0, "meanY": 0, "absMeanX": 0, "absMeanY": 0, "stdevX": 0, "stdevY": 0, "samples": 0},
            "rotation": {"mean": 0, "stdev": 0, "samples": 0},
            "height": {"mean": 0, "stdev": 0, "min": 0, "max": 0, "samples": 0},
        },
        "falseCallPatterns": {
            "total": 0,
            "share": 0,
            "byPartNumber": [],
            "byDefectType": [],
            "byProgram": [],
            "byFamily": [],
        },
        "yieldReliability": {
            "defectsPerBoard": 0,
            "falseCallsPerBoard": 0,
            "criticalPartsPareto": [],
            "dailyTrend": [],
            "familyShare": [],
            "densityMean": 0,
            "densityStdDev": 0,
        },
        "operatorLinkages": {"byOperator": [], "byProcess": []},
        "timeSeries": {"daily": []},
        "insights": {"highlights": [], "opportunities": [], "businessValue": []},
    }

    monkeypatch.setattr(routes, "build_part_report_payload", lambda start, end: sample_payload)
    monkeypatch.setattr(routes, "_load_report_css", lambda: "")
    monkeypatch.setattr(
        routes,
        "render_html_to_pdf",
        lambda html, base_url=None: (_ for _ in ()).throw(PdfGenerationError("pdf error")),
    )

    with app_instance.app_context():
        _login(client)
        resp = client.get("/reports/part/export?format=pdf")
    assert resp.status_code == 503
    assert resp.get_json() == {"message": "pdf error"}


def test_part_report_feature_lock(app_instance, monkeypatch):
    client = app_instance.test_client()
    original = routes._compose_feature_state

    def _locked(slug):
        if slug == "reports_part":
            return {"slug": slug, "status": "locked", "message": "Locked"}
        return original(slug)

    monkeypatch.setattr(routes, "_compose_feature_state", _locked)

    with app_instance.app_context():
        _login(client)
        resp = client.get("/reports/part")
        assert resp.status_code == 302
        assert resp.headers.get("Location", "").endswith("/home")

        resp = client.get("/api/reports/part")
        assert resp.status_code == 423
        assert resp.get_json()["error"] == "feature_locked"
