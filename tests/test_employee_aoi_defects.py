import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module  # noqa: E402
from app import create_app  # noqa: E402


class StubQuery:
    def __init__(self, table):
        self._table = table
        self._select = ['*']

    def select(self, columns='*'):
        self._select = [col.strip() for col in columns.split(',') if col.strip()]
        return self

    def execute(self):
        data = list(self._table)
        if self._select != ['*']:
            data = [
                {column: row.get(column) for column in self._select if column in row}
                for row in data
            ]
        return SimpleNamespace(data=data, count=len(data))


class StubSupabase:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}

    def table(self, name):
        table = self.tables.setdefault(name, [])
        return StubQuery(table)


@pytest.fixture
def employee_app(monkeypatch):
    supabase = StubSupabase()
    monkeypatch.setattr(app_module, 'create_client', lambda url, key: supabase)
    os.environ.setdefault('SECRET_KEY', 'test')
    os.environ.setdefault('SUPABASE_URL', 'http://localhost')
    os.environ.setdefault('SUPABASE_SERVICE_KEY', 'service')
    app = create_app()
    app.testing = True
    return app, supabase


def _login_employee(client):
    with client.session_transaction() as session:
        session['username'] = 'Employee'
        session['role'] = 'EMPLOYEE'


def test_employee_defect_endpoint_returns_unique_ids(employee_app):
    app, supabase = employee_app
    supabase.tables['defect'] = [
        {'id': 'DEF-2'},
        {'id': 'DEF-1'},
        {'id': 'DEF-2'},
        {'id': None},
        {'id': '   '},
    ]

    client = app.test_client()
    _login_employee(client)
    response = client.get('/employee/defects')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {'defects': ['DEF-1', 'DEF-2']}


def test_employee_submission_validates_defect_selection(employee_app, monkeypatch):
    app, _ = employee_app
    client = app.test_client()

    with app.app_context():
        from app.main import routes

        monkeypatch.setattr(routes, 'fetch_distinct_defect_ids', lambda: (['DEF-1'], None))

        inserted_records: list[dict] = []

        def fake_insert(record):
            inserted_records.append(record)
            return ([record], None)

        monkeypatch.setattr(routes, 'insert_aoi_report', fake_insert)

    _login_employee(client)
    base_payload = {
        'date': '2024-01-02',
        'shift': '1st',
        'operator': 'Op One',
        'customer': 'Example Customer',
        'program': 'Program A',
        'assembly': 'Assembly 1',
        'job_number': 'J123',
        'quantity_inspected': '10',
        'quantity_rejected': '1',
        'inspection_type': 'SMT',
    }

    response = client.post(
        '/employee/aoi_reports',
        json={**base_payload, 'defect_id': 'DEF-1'},
    )

    assert response.status_code == 201
    assert len(inserted_records) == 1
    assert inserted_records[0]['Defect ID'] == 'DEF-1'

    invalid_response = client.post(
        '/employee/aoi_reports',
        json={**base_payload, 'defect_id': 'UNKNOWN'},
    )

    assert invalid_response.status_code == 400
    error_payload = invalid_response.get_json()
    assert 'defect_id' in (error_payload.get('errors') or {})
    assert len(inserted_records) == 1
