import os
import re
import sys
import pytest

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
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


def _mock_payload(monkeypatch):
    sample_payload = {
        "shiftImg": "img",
        "shift1_total": 10,
        "shift1_reject_pct": 1,
        "shift2_total": 20,
        "shift2_reject_pct": 2,
        "shift_total_diff": 10,
        "shift_reject_pct_diff": 1,
        "assemblies": [
            {
                "assembly": "Asm1",
                "yield": 95.0,
                "pastAvg": 96.0,
                "operators": ["Op1"],
                "boards": 5,
                "currentRejects": 0,
                "pastRejectsAvg": 1,
                "fiTypicalRejects": 2,
                "overlayChart": "img",
            }
        ],
        "shift1": [
            {
                "operator": "Op1",
                "program": "Prog1",
                "assembly": "Asm1",
                "job": "J1",
                "inspected": 5,
                "rejected": 0,
            }
        ],
        "shift2": [
            {
                "operator": "Op2",
                "program": "Prog2",
                "assembly": "Asm2",
                "job": "J2",
                "inspected": 10,
                "rejected": 1,
            }
        ],
    }
    monkeypatch.setattr(
        routes,
        "build_aoi_daily_report_payload",
        lambda day, operator, assembly: sample_payload,
    )
    monkeypatch.setattr(routes, "_generate_aoi_daily_report_charts", lambda payload: {})



def test_export_aoi_daily_report_cover_fields(app_instance, monkeypatch):
    _mock_payload(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get(
            "/reports/aoi_daily/export?date=2024-06-01&show_cover=1&contact=help@example.com"
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "report_range:</b> 2024-06-01 - 2024-06-01" in html
        assert "&lt;help@example.com&gt;" in html
        assert re.search(
            r"generated_at:</b> \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} EST", html
        )
        assert "Prog1" in html and "Prog2" in html


def test_export_aoi_daily_report_default_contact(app_instance, monkeypatch):
    _mock_payload(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/aoi_daily/export?date=2024-06-01&show_cover=1")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "&lt;tschawtz@4spectra.com&gt;" in html


def test_shift_chart_description_rendered(app_instance, monkeypatch):
    sample_payload = {
        "shift1_total": 10,
        "shift1_reject_pct": 1,
        "shift2_total": 20,
        "shift2_reject_pct": 2,
        "shift_total_diff": 10,
        "shift_reject_pct_diff": 1,
        "shiftTotals": {
            "shift1": {"inspected": 10},
            "shift2": {"inspected": 20},
        },
        "assemblies": [{"assembly": "Asm1", "yield": 95.0, "pastAvg": 96.0}],
        "shift1": [
            {
                "operator": "Op1",
                "program": "Prog1",
                "assembly": "Asm1",
                "job": "J1",
                "inspected": 5,
                "rejected": 0,
            }
        ],
        "shift2": [
            {
                "operator": "Op2",
                "program": "Prog2",
                "assembly": "Asm2",
                "job": "J2",
                "inspected": 10,
                "rejected": 1,
            }
        ],
    }
    monkeypatch.setattr(
        routes, "build_aoi_daily_report_payload", lambda day, operator, assembly: sample_payload
    )
    monkeypatch.setattr(routes, "plt", None)

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/aoi_daily/export?date=2024-06-01")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert (
            "2nd shift inspected 10 more boards than 1st shift and had a reject rate 1.00 percentage points higher." in html
            and "chart-desc" in html
        )
        assert "1st Shift Total:</strong> 10" in html
        assert "1st Shift Reject %:</strong> 1%" in html
        assert "2nd Shift Total:</strong> 20" in html
        assert "2nd Shift Reject %:</strong> 2%" in html
        assert "Total Difference:</strong> 10" in html
        assert "Reject % Difference:</strong> 1%" in html


def test_assembly_detail_rendered(app_instance, monkeypatch):
    sample_payload = {
        "assemblies": [
            {
                "assembly": "Asm1",
                "yield": 90.0,
                "pastAvg": 95.0,
                "operators": ["Op1", "Op2"],
                "boards": 20,
                "currentRejects": 2,
                "pastRejectsAvg": 1.5,
                "fiTypicalRejects": 1,
                "metricsChart": "img",
            }
        ],
        "shift1": [],
        "shift2": [],
        "shiftTotals": {
            "shift1": {"inspected": 0, "rejected": 0},
            "shift2": {"inspected": 0, "rejected": 0},
        },
    }
    monkeypatch.setattr(
        routes, "build_aoi_daily_report_payload", lambda day, operator, assembly: sample_payload
    )
    monkeypatch.setattr(routes, "_generate_aoi_daily_report_charts", lambda payload: {})

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/aoi_daily/export?date=2024-06-01")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Asm1" in html
        assert "Operators:</strong> Op1, Op2" in html
        assert "Boards Processed:</strong> 20 boards" in html
        assert "Current Yield %</td><td>90.00%" in html
        assert re.search(r"Historical Yield \(Avg of All Past Jobs\)</td><td>\s*95.00%", html)
        assert "Current AOI Rejects</td><td>2 rejects" in html
        assert re.search(r"Past AOI Rejects \(Avg\)</td><td>\s*1.50 rejects", html)
        assert "Typical FI Rejects</td><td>1.00 rejects" in html
        assert '<img src="img" alt="Metrics Chart">' in html


def test_toc_on_cover_before_shift_summary(app_instance, monkeypatch):
    _mock_payload(monkeypatch)
    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/aoi_daily/export?date=2024-06-01&show_cover=1")
        assert resp.status_code == 200
        html = resp.data.decode()
        cover_idx = html.index('id="cover"')
        toc_idx = html.index("Table of Contents")
        shift_idx = html.index("Shift Comparison")
        assert cover_idx < toc_idx < shift_idx


def test_historical_yield_uses_all_jobs(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        rows = [
            {
                "Date": "2024-06-05",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J6",
                "Quantity Inspected": 100,
                "Quantity Rejected": 0,
                "Shift": "1",
                "Program": "Alpha",
            },
            {
                "Date": "2024-06-04",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J5",
                "Quantity Inspected": 100,
                "Quantity Rejected": 10,
                "Program": "Alpha",
            },
            {
                "Date": "2024-06-03",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J4",
                "Quantity Inspected": 100,
                "Quantity Rejected": 20,
                "Program": "Alpha",
            },
            {
                "Date": "2024-06-02",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J3",
                "Quantity Inspected": 100,
                "Quantity Rejected": 30,
                "Program": "Alpha",
            },
            {
                "Date": "2024-06-01",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J2",
                "Quantity Inspected": 100,
                "Quantity Rejected": 40,
                "Program": "Alpha",
            },
            {
                "Date": "2024-05-31",
                "Operator": "Op",
                "Assembly": "Asm1",
                "Job Number": "J1",
                "Quantity Inspected": 100,
                "Quantity Rejected": 50,
                "Program": "Alpha",
            },
        ]
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (rows, None))
        monkeypatch.setattr(routes, "fetch_fi_reports", lambda: ([], None))
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/api/reports/aoi_daily?date=2024-06-05")
        assert resp.status_code == 200
        data = resp.get_json()
        asm = data["assemblies"][0]
        assert asm["pastAvg"] == pytest.approx(70.0)
        assert asm["pastRejectsAvg"] == pytest.approx(30.0)
        assert data["shift1"][0]["program"] == "Alpha"


def test_smt_th_control_charts_render(app_instance, monkeypatch):
    aoi_rows = [
        {
            "Date": "2024-06-01",
            "Shift": "1",
            "Operator": "Op1",
            "Assembly": "Asm1",
            "Quantity Inspected": 10,
            "Quantity Rejected": 1,
        }
    ]
    moat_rows = [
        {
            "Report Date": "2024-05-30",
            "Model Name": "Asm1 SMT",
            "FalseCall Parts": 2,
            "Total Boards": 100,
        },
        {
            "Report Date": "2024-05-31",
            "Model Name": "Asm1 TH",
            "FalseCall Parts": 1,
            "Total Boards": 50,
        },
    ]
    monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
    monkeypatch.setattr(routes, "fetch_fi_reports", lambda: ([], None))
    monkeypatch.setattr(routes, "fetch_moat", lambda: (moat_rows, None))
    monkeypatch.setattr(routes, "_generate_aoi_daily_report_charts", lambda payload: {})
    monkeypatch.setattr(routes, "_fig_to_data_uri", lambda fig: "img")

    client = app_instance.test_client()
    with app_instance.app_context():
        with client.session_transaction() as sess:
            sess["username"] = "tester"
        resp = client.get("/reports/aoi_daily/export?date=2024-06-01")
        assert resp.status_code == 200
        html = resp.data.decode()
        chart_section = re.search(
            r'<div class="moat-charts">.*?</div>\s*</div>', html, re.DOTALL
        ).group(0)
        assert chart_section.count("<img") == 1
        assert "SMT" in chart_section and "TH" in chart_section


def test_moat_chart_averages_duplicates_and_legend(monkeypatch):
    moat_rows = [
        {
            "Report Date": "2024-05-30",
            "Model Name": "Asm1 SMT",
            "FalseCall Parts": 2,
            "Total Boards": 100,
        },
        {
            "Report Date": "2024-05-30",
            "Model Name": "Asm1 SMT",
            "FalseCall Parts": 8,
            "Total Boards": 100,
        },
        {
            "Report Date": "2024-05-31",
            "Model Name": "Asm1 SMT",
            "FalseCall Parts": 4,
            "Total Boards": 200,
        },
        {
            "Report Date": "2024-05-30",
            "Model Name": "Asm1 TH",
            "FalseCall Parts": 1,
            "Total Boards": 50,
        },
        {
            "Report Date": "2024-05-30",
            "Model Name": "Asm1 TH",
            "FalseCall Parts": 3,
            "Total Boards": 150,
        },
    ]

    class FakeAx:
        def __init__(self):
            self.plot_calls = []
            self.legend_kwargs = None

        def plot(self, dates, vals, **kwargs):
            self.plot_calls.append({"dates": dates, "vals": vals, "kwargs": kwargs})

        def axhline(self, *args, **kwargs):
            pass

        def set_ylabel(self, *args, **kwargs):
            pass

        def set_title(self, *args, **kwargs):
            pass

        def tick_params(self, *args, **kwargs):
            pass

        def legend(self, *args, **kwargs):
            self.legend_kwargs = kwargs

    fake_ax = FakeAx()

    class FakePlt:
        def subplots(self, *args, **kwargs):
            return object(), fake_ax

    monkeypatch.setattr(routes, "plt", FakePlt())
    monkeypatch.setattr(routes, "_fig_to_data_uri", lambda fig: "img")

    captured_vals = []

    def fake_limits(vals):
        captured_vals.append(list(vals))
        return 0.0, 0.0, 0.0

    monkeypatch.setattr(routes, "_compute_control_limits", fake_limits)

    result = routes._build_assembly_moat_charts("Asm1", moat_rows)
    assert result["overlayChart"] == "img"

    smt_call, th_call = fake_ax.plot_calls
    assert smt_call["dates"] == ["2024-05-30", "2024-05-31"]
    assert smt_call["vals"] == [pytest.approx(0.05), pytest.approx(0.02)]
    assert th_call["dates"] == ["2024-05-30"]
    assert th_call["vals"] == [pytest.approx(0.02)]
    assert captured_vals[0] == smt_call["vals"]
    assert captured_vals[1] == th_call["vals"]
    assert fake_ax.legend_kwargs == {"loc": "center left", "bbox_to_anchor": (1, 0.5)}
