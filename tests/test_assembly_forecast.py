import os
import pytest

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

import app as app_module
from app import create_app


@pytest.fixture
def app_instance(monkeypatch):
    monkeypatch.setattr(app_module, "create_client", lambda url, key: object())
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")
    app = create_app()
    return app


def _login(client):
    with client.session_transaction() as sess:
        sess["username"] = "tester"


def test_assembly_forecast_requires_login(app_instance):
    client = app_instance.test_client()
    resp = client.get("/tools/assembly-forecast")
    assert resp.status_code == 302
    assert "/login" in resp.location


def test_assembly_forecast_renders_when_authenticated(app_instance):
    client = app_instance.test_client()
    with app_instance.app_context():
        _login(client)
        resp = client.get("/tools/assembly-forecast")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Assembly Forecast" in html
        assert "assembly-inputs" in html


def test_api_assemblies_search(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        moat_rows = [
            {"Model Name": "Asm1 SMT"},
            {"Model Name": "Asm1 TH"},
            {"Model Name": "Asm2 TH"},
        ]
        aoi_rows = [
            {"Assembly": "Asm1", "Program": "SMT"},
            {"Assembly": "Asm3", "Program": "SMT"},
        ]
        monkeypatch.setattr(routes, "fetch_moat", lambda: (moat_rows, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        _login(client)
        resp = client.get("/api/assemblies/search")
        assert resp.status_code == 200
        assert resp.get_json() == ["Asm1", "Asm2", "Asm3"]


@pytest.mark.parametrize("query", ["asm-4", "asm 4"])
def test_api_assemblies_search_normalization(app_instance, monkeypatch, query):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        moat_rows = [{"Model Name": "Asm-4 SMT"}]
        aoi_rows = [{"Assembly": "Asm 4", "Program": "SMT"}]
        monkeypatch.setattr(routes, "fetch_moat", lambda: (moat_rows, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        _login(client)
        resp = client.get("/api/assemblies/search", query_string={"q": query})
        assert resp.status_code == 200
        assert set(resp.get_json()) == {"Asm-4", "Asm 4"}


def test_api_assemblies_forecast(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        moat_rows = [
            {
                "Model Name": "Asm1 SMT",
                "Total Boards": 100,
                "FalseCall Parts": 5,
                "Customer": "CustA",
            },
            {
                "Model Name": "Asm1 TH",
                "Total Boards": 50,
                "FalseCall Parts": 2,
                "Customer": "CustA",
            },
            {
                "Model Name": "Asm2 SMT",
                "total_boards": 50,
                "falsecall_parts": 2,
                "Customer": "CustB",
            },
        ]
        aoi_rows = [
            {
                "Assembly": "Asm1",
                "Program": "SMT",
                "Quantity Inspected": 80,
                "Quantity Rejected": 4,
                "Customer": "CustA",
            },
            {
                "Assembly": "Asm2",
                "Program": "SMT",
                "aoi_Quantity Inspected": 40,
                "aoi_Quantity Rejected": 1,
                "Customer": "CustB",
            },
        ]
        monkeypatch.setattr(routes, "fetch_moat", lambda: (moat_rows, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        _login(client)
        resp = client.post(
            "/api/assemblies/forecast", json={"assemblies": ["Asm1", "Asm2", "Asm3"]}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert {a["assembly"] for a in data["assemblies"]} == {"Asm1", "Asm2", "Asm3"}
        asm1 = next(a for a in data["assemblies"] if a["assembly"] == "Asm1")
        assert asm1["boards"] == pytest.approx(150.0)
        assert asm1["falseCalls"] == pytest.approx(7.0)
        assert asm1["avgFalseCalls"] == pytest.approx(7.0 / 150.0)
        assert asm1["predictedFalseCalls"] == pytest.approx(7.0)
        assert asm1["inspected"] == pytest.approx(80.0)
        assert asm1["rejected"] == pytest.approx(4.0)
        assert asm1["yield"] == pytest.approx(95.0)
        assert asm1["customer"] == "CustA"
        assert asm1["predictedRejects"] == pytest.approx(7.5)
        assert asm1["predictedYield"] == pytest.approx(95.0)
        assert asm1["ngRatio"] == pytest.approx(5.0)
        assert asm1["predictedNGsPerBoard"] == pytest.approx(0.05)
        assert asm1["predictedFCPerBoard"] == pytest.approx(7.0 / 150.0)
        assert asm1["customerYield"] == pytest.approx(95.0)
        assert not asm1["missing"]
        asm2 = next(a for a in data["assemblies"] if a["assembly"] == "Asm2")
        assert asm2["boards"] == pytest.approx(50.0)
        assert asm2["falseCalls"] == pytest.approx(2.0)
        assert asm2["avgFalseCalls"] == pytest.approx(0.04)
        assert asm2["predictedFalseCalls"] == pytest.approx(2.0)
        assert asm2["inspected"] == pytest.approx(40.0)
        assert asm2["rejected"] == pytest.approx(1.0)
        assert asm2["yield"] == pytest.approx(97.5)
        assert asm2["customer"] == "CustB"
        assert asm2["predictedRejects"] == pytest.approx(1.25)
        assert asm2["predictedYield"] == pytest.approx(97.5)
        assert asm2["ngRatio"] == pytest.approx(2.5)
        assert asm2["predictedNGsPerBoard"] == pytest.approx(0.025)
        assert asm2["predictedFCPerBoard"] == pytest.approx(0.04)
        assert asm2["customerYield"] == pytest.approx(97.5)
        assert not asm2["missing"]
        asm3 = next(a for a in data["assemblies"] if a["assembly"] == "Asm3")
        assert asm3["missing"]
        assert asm3["boards"] == pytest.approx(0.0)
        assert asm3["inspected"] == pytest.approx(0.0)
        assert asm3["ngRatio"] == pytest.approx(0.0)
        assert asm3["predictedNGsPerBoard"] == pytest.approx(0.0)
        assert asm3["predictedFCPerBoard"] == pytest.approx(0.0)
        assert asm3["customerYield"] == pytest.approx(0.0)


def test_api_assemblies_forecast_dash_query(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        moat_rows = [
            {
                "Model Name": "Asm 5 SMT",
                "Total Boards": 10,
                "FalseCall Parts": 1,
                "Customer": "CustA",
            }
        ]
        aoi_rows = [
            {
                "Assembly": "Asm 5",
                "Program": "SMT",
                "Quantity Inspected": 8,
                "Quantity Rejected": 0.4,
                "Customer": "CustA",
            }
        ]
        monkeypatch.setattr(routes, "fetch_moat", lambda: (moat_rows, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        _login(client)
        resp = client.post(
            "/api/assemblies/forecast", json={"assemblies": ["Asm-5"]}
        )
        assert resp.status_code == 200


def test_api_assemblies_forecast_model_name_with_revision(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        moat_rows = [
            {
                "Model Name": "Asm1 RevA SMT",
                "Total Boards": 100,
                "FalseCall Parts": 5,
                "Customer": "CustA",
            }
        ]
        aoi_rows = [
            {
                "Assembly": "Asm1",
                "Program": "SMT",
                "Quantity Inspected": 80,
                "Quantity Rejected": 4,
                "Customer": "CustA",
            }
        ]
        monkeypatch.setattr(routes, "fetch_moat", lambda: (moat_rows, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        _login(client)
        resp = client.post("/api/assemblies/forecast", json={"assemblies": ["Asm1"]})
        assert resp.status_code == 200
        data = resp.get_json()
        asm1 = next(a for a in data["assemblies"] if a["assembly"] == "Asm1")
        assert asm1["boards"] == pytest.approx(100.0)
        assert asm1["falseCalls"] == pytest.approx(5.0)
        assert asm1["inspected"] == pytest.approx(80.0)
        assert not asm1["missing"]


def test_api_assemblies_forecast_includes_aoi_only_programs(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        moat_rows = [
            {
                "Model Name": "Asm1 SMT",
                "Total Boards": 100,
                "FalseCall Parts": 5,
                "Customer": "CustA",
            }
        ]
        aoi_rows = [
            {
                "Assembly": "Asm1",
                "Program": "SMT",
                "Quantity Inspected": 80,
                "Quantity Rejected": 4,
                "Customer": "CustA",
            },
            {
                "Assembly": "Asm1",
                "Program": "TH",
                "Quantity Inspected": 20,
                "Quantity Rejected": 1,
                "Customer": "CustA",
            },
            {
                "Assembly": "Asm2",
                "Program": "SMT",
                "Quantity Inspected": 40,
                "Quantity Rejected": 1,
                "Customer": "CustB",
            },
        ]
        monkeypatch.setattr(routes, "fetch_moat", lambda: (moat_rows, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        _login(client)
        resp = client.post(
            "/api/assemblies/forecast", json={"assemblies": ["Asm1", "Asm2"]}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        asm1 = next(a for a in data["assemblies"] if a["assembly"] == "Asm1")
        assert asm1["boards"] == pytest.approx(100.0)
        assert asm1["inspected"] == pytest.approx(100.0)
        assert asm1["rejected"] == pytest.approx(5.0)
        asm2 = next(a for a in data["assemblies"] if a["assembly"] == "Asm2")
        assert asm2["boards"] == pytest.approx(0.0)
        assert asm2["inspected"] == pytest.approx(40.0)
        assert asm2["rejected"] == pytest.approx(1.0)
        assert not asm2["missing"]
