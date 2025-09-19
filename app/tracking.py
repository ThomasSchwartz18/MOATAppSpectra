"""Utilities for recording user interaction tracking data."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class Tracker:
    """Simple SQLite-backed tracker for session and click events."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_token TEXT UNIQUE,
                    user_id TEXT,
                    username TEXT,
                    user_role TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS click_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_token TEXT,
                    user_id TEXT,
                    user_role TEXT,
                    event_name TEXT NOT NULL,
                    context TEXT,
                    metadata TEXT,
                    occurred_at TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_token) REFERENCES sessions(session_token)
                )
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _normalise_timestamp(self, value: Any | None) -> str:
        if isinstance(value, datetime):
            dt = value.astimezone(timezone.utc)
        elif isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
        elif isinstance(value, str) and value:
            cleaned = value.strip()
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(cleaned)
            except ValueError:
                dt = datetime.now(tz=timezone.utc)
            else:
                dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        else:
            dt = datetime.now(tz=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        if not value:
            return None
        cleaned = value.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    def start_session(
        self,
        user_id: str | None,
        user_role: str | None,
        *,
        username: str | None = None,
        session_token: str | None = None,
        started_at: Any | None = None,
    ) -> str:
        token = session_token or str(uuid.uuid4())
        start_timestamp = self._normalise_timestamp(started_at)

        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "SELECT start_time, end_time FROM sessions WHERE session_token = ?",
                (token,),
            )
            row = cur.fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO sessions (session_token, user_id, username, user_role, start_time)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (token, user_id, username, user_role, start_timestamp),
                )
            else:
                existing_start = row["start_time"]
                existing_end = row["end_time"]
                if existing_end:
                    token = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO sessions (session_token, user_id, username, user_role, start_time)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (token, user_id, username, user_role, start_timestamp),
                    )
                elif not existing_start:
                    conn.execute(
                        """
                        UPDATE sessions
                        SET start_time = ?, user_id = ?, username = ?, user_role = ?
                        WHERE session_token = ?
                        """,
                        (start_timestamp, user_id, username, user_role, token),
                    )
            conn.commit()
        return token

    def end_session(
        self, session_token: str | None, *, ended_at: Any | None = None
    ) -> bool:
        if not session_token:
            return False
        end_timestamp = self._normalise_timestamp(ended_at)

        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "SELECT start_time FROM sessions WHERE session_token = ?",
                (session_token,),
            )
            row = cur.fetchone()
            if row is None:
                return False
            start_time = self._parse_timestamp(row["start_time"])
            end_time = self._parse_timestamp(end_timestamp)
            duration = None
            if start_time and end_time:
                duration = (end_time - start_time).total_seconds()
            conn.execute(
                """
                UPDATE sessions
                SET end_time = ?, duration_seconds = ?
                WHERE session_token = ?
                """,
                (end_timestamp, duration, session_token),
            )
            conn.commit()
        return True

    def record_click(
        self,
        session_token: str | None,
        user_id: str | None,
        user_role: str | None,
        event_name: str,
        *,
        context: dict[str, Any] | str | None = None,
        metadata: dict[str, Any] | None = None,
        occurred_at: Any | None = None,
    ) -> None:
        if not event_name:
            raise ValueError("event_name is required")

        context_payload: str | None
        if context is None:
            context_payload = None
        elif isinstance(context, str):
            context_payload = context
        else:
            context_payload = json.dumps(context, ensure_ascii=False)

        metadata_payload = (
            json.dumps(metadata, ensure_ascii=False) if metadata is not None else None
        )

        occurred_timestamp = self._normalise_timestamp(occurred_at)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO click_events (
                    session_token,
                    user_id,
                    user_role,
                    event_name,
                    context,
                    metadata,
                    occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_token,
                    user_id,
                    user_role,
                    event_name,
                    context_payload,
                    metadata_payload,
                    occurred_timestamp,
                ),
            )
            conn.commit()


__all__ = ["Tracker"]
