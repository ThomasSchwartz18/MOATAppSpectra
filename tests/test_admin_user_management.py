import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("USER_PASSWORD", "pw")
os.environ.setdefault("ADMIN_PASSWORD", "pw")

import app as app_module
from app import create_app


class FakeQuery:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self._operation = None
        self._payload = None
        self._filters = []
        self._limit = None
        self._select = "*"

    def select(self, columns="*"):
        self._operation = "select"
        self._select = columns
        return self

    def insert(self, rows):
        self._operation = "insert"
        self._payload = rows
        return self

    def delete(self):
        self._operation = "delete"
        return self

    def eq(self, column, value):
        self._filters.append(("eq", column, value))
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, value):
        self._limit = value
        return self

    def execute(self):
        table = self.supabase.tables.setdefault(self.table_name, [])
        if self._operation == "select":
            data = list(table)
            for op, column, value in self._filters:
                if op == "eq":
                    data = [row for row in data if row.get(column) == value]
            if self._limit is not None:
                data = data[: self._limit]
            if self._select != "*":
                columns = [col.strip() for col in self._select.split(",")]
                data = [
                    {col: row.get(col) for col in columns if col in row}
                    for row in data
                ]
            return SimpleNamespace(data=data, count=len(data))
        if self._operation == "insert":
            rows = self._payload
            if isinstance(rows, dict):
                rows = [rows]
            inserted = []
            for row in rows:
                new_row = row.copy()
                new_row.setdefault(
                    "id", f"fake-{len(table) + len(inserted) + 1}"
                )
                table.append(new_row)
                inserted.append(new_row)
            return SimpleNamespace(data=inserted, count=len(inserted))
        if self._operation == "delete":
            deleted = []
            remaining = []
            for row in table:
                match = True
                for op, column, value in self._filters:
                    if op == "eq" and row.get(column) != value:
                        match = False
                        break
                if match and self._filters:
                    deleted.append(row)
                else:
                    remaining.append(row)
            if not self._filters:
                deleted = table[:]
                remaining = []
            self.supabase.tables[self.table_name] = remaining
            return SimpleNamespace(data=deleted, count=len(deleted))
        return SimpleNamespace(data=None, count=None)


class FakeSupabase:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}

    def table(self, name):
        return FakeQuery(self, name)


@pytest.fixture
def admin_app(monkeypatch):
    fake_supabase = FakeSupabase()
    monkeypatch.setattr(app_module, "create_client", lambda url, key: fake_supabase)
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")
    app = create_app()
    app.testing = True
    return app, fake_supabase


def _login_admin(client):
    with client.session_transaction() as sess:
        sess["username"] = "ADMIN"
        sess["role"] = "ADMIN"


def test_admin_can_create_supabase_user(admin_app):
    app, supabase = admin_app
    client = app.test_client()
    _login_admin(client)

    response = client.post(
        "/admin/users",
        data={
            "action": "invite",
            "username": "analyst",
            "display_name": "Ana Analyst",
            "role": "ANALYST",
            "temporary_password": "s3cret",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    stored = supabase.tables.get("app_users", [])
    assert len(stored) == 1
    user = stored[0]
    assert user["username"] == "analyst"
    assert user["display_name"] == "Ana Analyst"
    assert user["role"] == "ANALYST"
    assert user.get("must_reset_password") is True
    assert check_password_hash(user["password_hash"], "s3cret")


def test_admin_can_remove_supabase_user(admin_app):
    app, supabase = admin_app
    supabase.tables["app_users"] = [
        {
            "id": "fake-1",
            "username": "tempuser",
            "display_name": "Temp User",
            "role": "USER",
            "password_hash": generate_password_hash("temp"),
        }
    ]
    client = app.test_client()
    _login_admin(client)

    response = client.post(
        "/admin/users",
        data={"action": "remove", "username": "tempuser"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert supabase.tables["app_users"] == []
    assert b"has been removed" in response.data


def test_login_uses_supabase_accounts(admin_app):
    app, supabase = admin_app
    supabase.tables["app_users"] = [
        {
            "id": "fake-42",
            "username": "analyst",
            "display_name": "Ana Analyst",
            "role": "ANALYST",
            "password_hash": generate_password_hash("s3cret"),
        }
    ]
    client = app.test_client()

    get_response = client.get("/login")
    assert get_response.status_code == 200
    assert b"Ana Analyst" in get_response.data

    response = client.post(
        "/login",
        data={"username": "Analyst", "password": "s3cret"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/home")
    with client.session_transaction() as sess:
        assert sess["username"] == "Ana Analyst"
        assert sess["role"] == "ANALYST"
