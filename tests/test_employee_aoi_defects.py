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
def test_employee_submission_succeeds_without_defect_dropdown(employee_app, monkeypatch):
    app, _ = employee_app
    client = app.test_client()

    with app.app_context():
        from app.main import routes

        inserted_records: list[dict] = []

        def fake_insert(record):
            inserted_records.append(record)
            return ([record], None)

        monkeypatch.setattr(routes, 'insert_aoi_report', fake_insert)
        monkeypatch.setattr(routes, 'ensure_customer', lambda name: (1, None))
        monkeypatch.setattr(
            routes,
            'ensure_customer_assembly',
            lambda customer_id, assembly, rev: (1, None),
        )
        monkeypatch.setattr(routes, 'ensure_operator', lambda name, role: (1, None))
        monkeypatch.setattr(routes, 'ensure_job', lambda job_number, **kwargs: (1, None))

    _login_employee(client)
    base_payload = {
        'date': '2024-01-02',
        'shift': '1st',
        'operator': 'Op One',
        'customer': 'Example Customer',
        'program': 'SMT',
        'area': 'AOI',
        'assembly': 'Assembly 1',
        'job_number': 'J123',
        'quantity_inspected': '10',
        'quantity_rejected': '0',
        'inspection_type': 'SMT',
        'operator_signature_acknowledged': 'true',
    }

    response = client.post('/employee/aoi_reports', json=base_payload)
    assert response.status_code == 201
    assert len(inserted_records) == 1
    record = inserted_records[0]
    assert record['program'] == 'SMT'
    assert record['quantity_inspected'] == 10
    assert record['quantity_rejected'] == 0
    assert record.get('additional_information') is None or record.get('additional_information') == ""
    assert record['assembly_id'] == 1
    assert record['customer_id'] == 1
    assert record['operator_id'] == 1
    assert 'operator' not in record
    assert 'assembly' not in record
    assert 'operator' not in record
    assert 'assembly' not in record


def test_employee_submission_formats_rejection_details(employee_app, monkeypatch):
    app, _ = employee_app
    client = app.test_client()

    with app.app_context():
        from app.main import routes

        inserted_records: list[dict] = []

        def fake_insert(record):
            inserted_records.append(record)
            return ([record], None)

        monkeypatch.setattr(routes, 'insert_aoi_report', fake_insert)
        monkeypatch.setattr(routes, 'ensure_customer', lambda name: (1, None))
        monkeypatch.setattr(
            routes,
            'ensure_customer_assembly',
            lambda customer_id, assembly, rev: (1, None),
        )
        monkeypatch.setattr(routes, 'ensure_operator', lambda name, role: (1, None))
        monkeypatch.setattr(routes, 'ensure_job', lambda job_number, **kwargs: (1, None))

    _login_employee(client)

    payload = {
        'date': '2024-02-03',
        'shift': '2nd',
        'operator': 'Operator Two',
        'customer': 'Customer B',
        'program': 'TH',
        'area': 'AOI',
        'assembly': 'Assembly 2',
        'job_number': 'J456',
        'quantity_inspected': '25',
        'quantity_rejected': '3',
        'inspection_type': 'SMT',
        'notes': 'Needs review',
        'rejection_details': [
            {'ref': 'R15', 'reason': 'Bent lead', 'reason_id': 'th-POR', 'quantity': 2},
            {'ref': 'R22', 'reason': ' Tombstone ', 'reason_id': 'smt-TOS', 'quantity': 1},
        ],
        'operator_signature_acknowledged': 'true',
    }

    response = client.post('/employee/aoi_reports', json=payload)

    assert response.status_code == 201
    assert inserted_records
    record = inserted_records[0]
    additional = record.get('additional_information')
    assert additional == 'R15 th-POR (2),\nR22 smt-TOS (1)\nNotes: Needs review'
    assert record['assembly_id'] == 1
    assert record['customer_id'] == 1
    assert record['operator_id'] == 1


def test_employee_submission_rejects_invalid_rejection_rows(employee_app, monkeypatch):
    app, _ = employee_app
    client = app.test_client()

    with app.app_context():
        from app.main import routes

        def fake_insert(record):
            raise AssertionError('Should not insert invalid record')

        monkeypatch.setattr(routes, 'insert_aoi_report', fake_insert)
        monkeypatch.setattr(routes, 'ensure_customer', lambda name: (1, None))
        monkeypatch.setattr(
            routes,
            'ensure_customer_assembly',
            lambda customer_id, assembly, rev: (1, None),
        )
        monkeypatch.setattr(routes, 'ensure_operator', lambda name, role: (1, None))
        monkeypatch.setattr(routes, 'ensure_job', lambda job_number, **kwargs: (1, None))

    _login_employee(client)

    payload = {
        'date': '2024-02-04',
        'shift': '1st',
        'operator': 'Operator Three',
        'customer': 'Customer C',
        'program': 'SMT',
        'area': 'AOI',
        'assembly': 'Assembly 3',
        'job_number': 'J789',
        'quantity_inspected': '30',
        'quantity_rejected': '2',
        'inspection_type': 'SMT',
        'rejection_details': [
            {'ref': '', 'reason': 'Bent lead', 'quantity': 2},
            {'ref': 'R30', 'reason': 'Missing component', 'quantity': 0},
        ],
        'operator_signature_acknowledged': 'true',
    }

    response = client.post('/employee/aoi_reports', json=payload)

    assert response.status_code == 400
    payload = response.get_json()
    assert 'rejection_details' in (payload.get('errors') or {})


def test_employee_submission_requires_operator_signature(employee_app, monkeypatch):
    app, _ = employee_app
    client = app.test_client()

    with app.app_context():
        from app.main import routes

        def fake_insert(record):
            raise AssertionError('Should not insert without signature')

        monkeypatch.setattr(routes, 'insert_aoi_report', fake_insert)
        monkeypatch.setattr(routes, 'ensure_customer', lambda name: (1, None))
        monkeypatch.setattr(
            routes,
            'ensure_customer_assembly',
            lambda customer_id, assembly, rev: (1, None),
        )
        monkeypatch.setattr(routes, 'ensure_operator', lambda name, role: (1, None))
        monkeypatch.setattr(routes, 'ensure_job', lambda job_number, **kwargs: (1, None))

    _login_employee(client)

    payload = {
        'date': '2024-03-01',
        'shift': '1st',
        'operator': 'Operator Four',
        'customer': 'Customer D',
        'program': 'SMT',
        'area': 'AOI',
        'assembly': 'Assembly 4',
        'job_number': 'J101',
        'quantity_inspected': '15',
        'quantity_rejected': '0',
        'inspection_type': 'SMT',
        'operator_signature_acknowledged': '',
    }

    response = client.post('/employee/aoi_reports', json=payload)

    assert response.status_code == 400
    response_payload = response.get_json() or {}
    assert 'operator_signature_acknowledged' in (response_payload.get('errors') or {})
