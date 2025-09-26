import os

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

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


def _login(client, role=None):
    with client.session_transaction() as session:
        session["username"] = "tester"
        if role:
            session["role"] = role


def _make_fetch(rows, error=None):
    return lambda *args, rows=rows, error=error, **kwargs: (rows, error)


class _TrackerCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _TrackerConnection:
    def __init__(self, session_rows, event_rows):
        self._session_rows = session_rows
        self._event_rows = event_rows

    def execute(self, query, params=()):
        query_lower = query.lower()
        if 'from sessions' in query_lower:
            return _TrackerCursor(self._session_rows)
        if 'from click_events' in query_lower:
            return _TrackerCursor(self._event_rows)
        raise AssertionError(f'Unexpected query: {query}')


class _TrackerStub:
    def __init__(self, session_rows, event_rows):
        self._session_rows = session_rows
        self._event_rows = event_rows

    @contextmanager
    def _connect(self):
        yield _TrackerConnection(self._session_rows, self._event_rows)


def _current_day():
    return datetime.now(timezone.utc).date()


def _moat_preview_patch():
    today = _current_day()
    ppm_rows = [
        {
            "Model Name": "Asm1 SMT",
            "Total Boards": 120,
            "FalseCall Parts": 6,
            "Report Date": today.isoformat(),
        },
        {
            "Model Name": "Asm2 SMT",
            "Total Boards": 80,
            "FalseCall Parts": 4,
            "Report Date": (today - timedelta(days=1)).isoformat(),
        },
    ]
    dpm_rows = [
        {
            "Model Name": "Asm1 SMT",
            "Total Boards": 120,
            "FalseCall Windows": 6,
            "Windows per board": 1,
            "Total Windows": 120,
            "Report Date": today.isoformat(),
        },
        {
            "Model Name": "Asm2 SMT",
            "Total Boards": 80,
            "FalseCall Windows": 4,
            "Windows per board": 1,
            "Total Windows": 80,
            "Report Date": (today - timedelta(days=1)).isoformat(),
        },
    ]
    return {
        "fetch_recent_moat": _make_fetch(ppm_rows),
        "fetch_recent_moat_dpm": _make_fetch(dpm_rows),
    }


def _aoi_preview_patch():
    today = _current_day()
    rows = [
        {
            "Date": today.isoformat(),
            "Quantity Inspected": 150,
            "Quantity Rejected": 5,
        },
        {
            "Date": (today - timedelta(days=1)).isoformat(),
            "Quantity Inspected": 140,
            "Quantity Rejected": 4,
        },
    ]
    return {"fetch_aoi_reports": _make_fetch(rows)}


def _fi_preview_patch():
    today = _current_day()
    rows = [
        {
            "Date": today.isoformat(),
            "Quantity Inspected": 110,
            "Quantity Rejected": 3,
        },
        {
            "Date": (today - timedelta(days=1)).isoformat(),
            "Quantity Inspected": 115,
            "Quantity Rejected": 2,
        },
    ]
    return {"fetch_fi_reports": _make_fetch(rows)}


def _daily_preview_patch():
    today = _current_day()
    rows = [
        {
            "aoi_Date": today.isoformat(),
            "aoi_Quantity Inspected": 160,
            "aoi_Quantity Rejected": 6,
        },
        {
            "fi_Date": (today - timedelta(days=1)).isoformat(),
            "fi_Quantity Inspected": 130,
            "fi_Quantity Rejected": 4,
        },
    ]
    return {"fetch_combined_reports": _make_fetch(rows)}


def _forecast_preview_patch():
    today = _current_day()
    moat_rows = [
        {
            "Model Name": "Asm1 SMT",
            "Total Boards": 200,
            "FalseCall Parts": 10,
            "Report Date": (today - timedelta(days=1)).isoformat(),
        }
    ]
    aoi_rows = [
        {
            "Assembly": "Asm1",
            "Program": "SMT",
            "Quantity Inspected": 180,
            "Quantity Rejected": 8,
            "Date": today.isoformat(),
        }
    ]
    return {
        "fetch_recent_moat": _make_fetch(moat_rows),
        "fetch_aoi_reports": _make_fetch(aoi_rows),
    }


def _bug_preview_patch():
    today = _current_day()
    rows = [
        {
            "status": "open",
            "created_at": f"{today.isoformat()}T08:15:00+00:00",
        },
        {
            "status": "resolved",
            "created_at": f"{today.isoformat()}T12:30:00+00:00",
        },
        {
            "status": "closed",
            "created_at": f"{(today - timedelta(days=1)).isoformat()}T09:00:00+00:00",
        },
    ]
    return {"fetch_bug_reports": _make_fetch(rows)}


def _tracker_preview_patch():
    today = _current_day()
    session_rows = [
        {
            'session_token': 'abc',
            'start_time': f'{today.isoformat()}T09:00:00+00:00',
            'end_time': f'{today.isoformat()}T09:05:00+00:00',
            'duration_seconds': 300,
        },
        {
            'session_token': 'def',
            'start_time': f'{today.isoformat()}T10:00:00+00:00',
            'end_time': None,
            'duration_seconds': None,
        },
    ]

    event_rows = [
        {
            'session_token': 'abc',
            'event_name': 'navigate',
            'context': json.dumps({'href': '/home', 'text': 'Home'}),
            'metadata': None,
            'occurred_at': f'{today.isoformat()}T09:01:30+00:00',
        },
        {
            'session_token': 'abc',
            'event_name': 'navigate',
            'context': json.dumps({'href': '/home', 'text': 'Home'}),
            'metadata': None,
            'occurred_at': f'{today.isoformat()}T09:02:45+00:00',
        },
        {
            'session_token': 'def',
            'event_name': 'navigate',
            'context': json.dumps({'href': '/reports', 'text': 'Reports'}),
            'metadata': None,
            'occurred_at': f'{today.isoformat()}T10:02:00+00:00',
        },
    ]

    tracker = _TrackerStub(session_rows, event_rows)
    return {'_get_tracker': lambda: tracker}


PREVIEW_CASES = [
    ("/moat_preview", _moat_preview_patch),
    ("/moat_preview?source=dpm", _moat_preview_patch),
    ("/aoi_preview", _aoi_preview_patch),
    ("/fi_preview", _fi_preview_patch),
    ("/daily_reports_preview", _daily_preview_patch),
    ("/forecast_preview", _forecast_preview_patch),
    ("/bug_reports_preview", _bug_preview_patch),
    ("/tracker_preview", _tracker_preview_patch),
]


@pytest.mark.parametrize("endpoint, patch_factory", PREVIEW_CASES)
def test_home_dashboard_previews_return_expected_fields(
    app_instance, monkeypatch, endpoint, patch_factory
):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        for attr, replacement in patch_factory().items():
            monkeypatch.setattr(routes, attr, replacement)

        _login(client)
        response = client.get(endpoint)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert "labels" in payload
    assert {"values", "yields"} & payload.keys()
    assert ("start_date" in payload) or ("start_time" in payload)
    assert ("end_date" in payload) or ("end_time" in payload)
    if endpoint == "/bug_reports_preview":
        assert "summary" in payload
        assert payload["summary"]["total_reports"] == 3
    if endpoint == "/tracker_preview":
        assert payload["total_sessions"] == 2
        assert payload["total_navigation_events"] == 3
        assert payload["total_backtracking_events"] == 1
        assert (
            payload["summary_text"]
            == f"Average Time: {payload['average_duration_label']}"
        )


def test_home_admin_renders_diagnostics(app_instance, monkeypatch):
    client = app_instance.test_client()
    diagnostics = {
        "status": "Connected",
        "error": "Supabase service offline",
        "tables": [
            {
                "name": "aoi_reports",
                "status": "Unavailable",
                "error": "Table missing",
                "description": "AOI inspection uploads used across the AOI dashboards.",
            }
        ],
    }

    with app_instance.app_context():
        from app.main import routes

        monkeypatch.setattr(routes, "_summarize_supabase_status", lambda: diagnostics)

    _login(client, role="ADMIN")
    response = client.get("/home")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Supabase service offline" in html
    assert "Table missing" in html


def test_admin_employee_portal_route_renders_employee_template(app_instance):
    client = app_instance.test_client()

    _login(client, role="ADMIN")
    response = client.get("/admin/employee-portal")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Employee Portal" in html
    assert "Select your area" in html


def test_admin_employee_portal_requires_admin_role(app_instance):
    client = app_instance.test_client()

    _login(client, role="USER")
    response = client.get("/admin/employee-portal")

    assert response.status_code == 403


def test_admin_preview_toggle_visible_for_admin(app_instance, monkeypatch):
    client = app_instance.test_client()

    with app_instance.app_context():
        from app.main import routes

        monkeypatch.setattr(
            routes,
            "_summarize_supabase_status",
            lambda: {"status": "Connected", "tables": [], "checked_at": None},
        )
        monkeypatch.setattr(routes, "_fetch_configured_users", lambda: ([], None))
        monkeypatch.setattr(routes, "fetch_bug_reports", lambda: ([], None))
        monkeypatch.setattr(routes, "_build_feature_cards", lambda records: ([], {}))
        monkeypatch.setattr(routes, "_build_bug_options", lambda records: [])

    _login(client, role="ADMIN")
    response = client.get("/home")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-admin-employee-toggle' in html
    assert 'data-employee-url="/admin/employee-portal' in html


def test_employee_portal_link_hidden_for_non_admin(app_instance):
    client = app_instance.test_client()

    _login(client, role="EMPLOYEE")
    response = client.get("/home")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-admin-employee-toggle' not in html


def test_admin_employee_portal_preview_uses_employee_layout(app_instance):
    client = app_instance.test_client()

    _login(client, role="ADMIN")
    response = client.get("/admin/employee-portal?return=/home")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<body class="employee-layout"' in html
    assert '<header class="app-header"' not in html
    assert 'data-admin-employee-toggle' in html
    assert 'data-admin-url="/home"' in html
    assert 'data-preview-active="true"' in html
