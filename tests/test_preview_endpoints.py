import os
from contextlib import contextmanager
from datetime import datetime, timedelta
import json

import pytest

import app as app_module
from app import create_app


os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")


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


def _recent_dates(count=3):
    today = datetime.utcnow().date()
    return [today - timedelta(days=offset) for offset in range(count)]


def _assert_preview_keys(data):
    assert 'labels' in data
    assert 'values' in data
    assert ('start_date' in data) or ('start_time' in data)
    assert ('end_date' in data) or ('end_time' in data)


class _DummyCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _DummyConnection:
    def __init__(self, session_rows, event_rows):
        self._session_rows = session_rows
        self._event_rows = event_rows

    def execute(self, query, params=()):
        query_lower = query.lower()
        if 'from sessions' in query_lower:
            return _DummyCursor(self._session_rows)
        if 'from click_events' in query_lower:
            return _DummyCursor(self._event_rows)
        raise AssertionError(f'Unexpected query: {query}')


class DummyTracker:
    def __init__(self, session_rows, event_rows):
        self._session_rows = session_rows
        self._event_rows = event_rows

    @contextmanager
    def _connect(self):
        yield _DummyConnection(self._session_rows, self._event_rows)


def test_moat_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        d0, d1 = _recent_dates(2)
        moat_rows = [
            {
                "Model Name": "Asm1 SMT",
                "FalseCall Parts": 5,
                "Total Boards": 100,
                "Report Date": d0.isoformat(),
            },
            {
                "Model Name": "Asm2 SMT",
                "falsecall_parts": 2,
                "total_boards": 50,
                "report_date": d1.isoformat(),
            },
        ]
        monkeypatch.setattr(routes, "fetch_recent_moat", lambda: (moat_rows, None))
        _login(client)
        resp = client.get("/moat_preview")
        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert set(data["labels"]) == {"Asm1 SMT", "Asm2 SMT"}
        assert len(data["labels"]) == len(data["values"])


def test_aoi_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        d0, d1 = _recent_dates(2)
        aoi_rows = [
            {
                "Date": d0.isoformat(),
                "Quantity Inspected": 100,
                "Quantity Rejected": 5,
            },
            {
                "date": d1.isoformat(),
                "quantity_inspected": 80,
                "quantity_rejected": 4,
            },
        ]
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        _login(client)
        resp = client.get("/aoi_preview")
        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert len(data["labels"]) == len(data["values"])


def test_fi_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        d0, d1 = _recent_dates(2)
        fi_rows = [
            {
                "Date": d0.isoformat(),
                "Quantity Inspected": 120,
                "Quantity Rejected": 6,
            },
            {
                "date": d1.isoformat(),
                "quantity_inspected": 150,
                "quantity_rejected": 3,
            },
        ]
        monkeypatch.setattr(routes, "fetch_fi_reports", lambda: (fi_rows, None))
        _login(client)
        resp = client.get("/fi_preview")
        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert len(data["labels"]) == len(data["values"])


def test_bug_reports_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        today, yesterday = _recent_dates(2)
        bug_rows = [
            {
                "status": "Open",
                "created_at": f"{today.isoformat()}T08:00:00+00:00",
            },
            {
                "status": "resolved",
                "created_at": f"{today.isoformat()}T12:00:00+00:00",
            },
            {
                "status": "closed",
                "created_at": f"{yesterday.isoformat()}T09:30:00+00:00",
            },
            {
                "status": "open",
                "created_at": f"{(today - timedelta(days=10)).isoformat()}T00:00:00+00:00",
            },
        ]

        monkeypatch.setattr(routes, "fetch_bug_reports", lambda: (bug_rows, None))
        _login(client)
        resp = client.get("/bug_reports_preview")

        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert "summary" in data

        summary = data["summary"]
        assert summary["total_reports"] == 3
        assert summary["resolved_reports"] == 2
        assert summary["active_reports"] == 1
        assert summary["window_days"] == 7
        assert summary["start_date"] == yesterday.isoformat()
        assert summary["end_date"] == today.isoformat()
        assert set(data["labels"]) >= {"Open", "Resolved", "Closed"}
        assert len(data["labels"]) == len(data["values"])


def test_tracker_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        session_rows = [
            {
                'session_token': 'abc',
                'start_time': '2024-05-01T10:00:00+00:00',
                'end_time': '2024-05-01T10:06:00+00:00',
                'duration_seconds': 360,
            },
            {
                'session_token': 'def',
                'start_time': '2024-05-01T11:00:00+00:00',
                'end_time': None,
                'duration_seconds': None,
            },
        ]

        event_rows = [
            {
                'session_token': 'abc',
                'event_name': 'navigate',
                'context': json.dumps({'href': '/dashboard', 'text': 'Dashboard'}),
                'metadata': None,
                'occurred_at': '2024-05-01T10:01:00+00:00',
            },
            {
                'session_token': 'abc',
                'event_name': 'navigate',
                'context': json.dumps({'href': '/dashboard', 'text': 'Dashboard'}),
                'metadata': None,
                'occurred_at': '2024-05-01T10:02:30+00:00',
            },
            {
                'session_token': 'def',
                'event_name': 'navigate',
                'context': json.dumps({'href': '/reports', 'text': 'Reports'}),
                'metadata': None,
                'occurred_at': '2024-05-01T11:01:15+00:00',
            },
            {
                'session_token': 'def',
                'event_name': 'click',
                'context': None,
                'metadata': None,
                'occurred_at': '2024-05-01T11:02:30+00:00',
            },
        ]

        tracker = DummyTracker(session_rows, event_rows)
        monkeypatch.setattr(routes, '_get_tracker', lambda: tracker)

        _login(client)
        resp = client.get('/tracker_preview')
        assert resp.status_code == 200

        data = resp.get_json()
        assert data
        assert data['labels'] == ['Sessions', 'Events', 'Navigation', 'Backtracking']
        assert data['values'][0] == len(session_rows)
        assert data['total_sessions'] == len(session_rows)
        assert data['total_events'] == len(event_rows)
        assert data['total_navigation_events'] == 3
        assert data['total_backtracking_events'] == 1
        assert data['average_duration_seconds'] is not None
        assert data['average_duration_label']
        assert data['summary_text']
        assert ('start_time' in data and data['start_time']) or (
            'start_date' in data and data['start_date']
        )


def test_daily_reports_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        d0, d1, d2 = _recent_dates(3)
        combined_rows = [
            {
                "aoi_Date": d0.isoformat(),
                "aoi_Quantity Inspected": 90,
                "aoi_Quantity Rejected": 5,
            },
            {
                "Date": d1.isoformat(),
                "Quantity Inspected": 110,
                "Quantity Rejected": 4,
            },
            {
                "fi_Date": d2.isoformat(),
                "fi_Quantity Inspected": 100,
                "fi_Quantity Rejected": 6,
            },
        ]
        monkeypatch.setattr(
            routes, "fetch_combined_reports", lambda: (combined_rows, None)
        )
        _login(client)
        resp = client.get("/daily_reports_preview")
        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert "avg_yield" in data
        assert len(data["labels"]) == len(data["values"])


def test_forecast_preview_returns_summary(app_instance, monkeypatch):
    client = app_instance.test_client()
    with app_instance.app_context():
        from app.main import routes

        d0, d1 = _recent_dates(2)
        moat_rows = [
            {
                "Model Name": "Asm1 SMT",
                "Total Boards": 100,
                "FalseCall Parts": 5,
                "Report Date": d0.isoformat(),
            },
            {
                "Model Name": "Asm2 SMT",
                "Total Boards": 80,
                "FalseCall Parts": 4,
                "Report Date": d1.isoformat(),
            },
        ]
        aoi_rows = [
            {
                "Assembly": "Asm1",
                "Program": "SMT",
                "Quantity Inspected": 90,
                "Quantity Rejected": 3,
                "Date": d0.isoformat(),
            },
            {
                "Assembly": "Asm2",
                "Program": "SMT",
                "Quantity Inspected": 70,
                "Quantity Rejected": 2,
                "Date": d1.isoformat(),
            },
        ]
        monkeypatch.setattr(routes, "fetch_recent_moat", lambda: (moat_rows, None))
        monkeypatch.setattr(routes, "fetch_aoi_reports", lambda: (aoi_rows, None))
        _login(client)
        resp = client.get("/forecast_preview")
        assert resp.status_code == 200
        data = resp.get_json()
        _assert_preview_keys(data)
        assert data["labels"]
        assert len(data["labels"]) == len(data["values"])
