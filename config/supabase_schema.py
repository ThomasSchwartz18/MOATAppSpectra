"""Centralised Supabase table and column configuration.

The application interacts with a number of Supabase/PostgREST tables.  Each
table name and column identifier used by the code base is defined here so that
deployments can adjust naming conventions without needing to modify
application logic.  When a mapping for a particular table or column is not
present the helper functions gracefully fall back to the identifier supplied by
the caller, preserving backwards compatibility while still allowing overrides
via this configuration file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class SupabaseTable:
    """Configuration for a Supabase table."""

    name: str
    columns: Mapping[str, str] = field(default_factory=dict)


# Table and column mappings may be customised by editing the values below.
# The keys (e.g. ``"app_versions"``) are stable identifiers used throughout the
# code base; ``name`` is the actual table name in Supabase and ``columns`` maps
# logical column identifiers to their Supabase counterparts.
SUPABASE_SCHEMA: Dict[str, SupabaseTable] = {
    "app_versions": SupabaseTable(
        name="app_versions",
        columns={
            "id": "id",
            "platform": "platform",
            "version": "version",
            "download_url": "download_url",
            "checksum": "checksum",
            "release_notes": "release_notes",
            "updated_at": "updated_at",
        },
    ),
    "app_feature_states": SupabaseTable(
        name="app_feature_states",
        columns={
            "id": "id",
            "slug": "slug",
            "status": "status",
            "message": "message",
            "bug_report_id": "bug_report_id",
            "updated_at": "updated_at",
        },
    ),
    "app_users": SupabaseTable(
        name="app_users",
        columns={
            "id": "id",
            "username": "username",
            "display_name": "display_name",
            "email": "email",
            "password_hash": "password_hash",
            "role": "role",
            "auth_user_id": "auth_user_id",
            "auth_user": "auth_user",
        },
    ),
    "bug_reports": SupabaseTable(
        name="bug_reports",
        columns={
            "id": "id",
            "title": "title",
            "description": "description",
            "status": "status",
            "created_at": "created_at",
            "updated_at": "updated_at",
            "reporter_id": "reporter_id",
            "reporter_name": "reporter_name",
        },
    ),
    "aoi_reports": SupabaseTable(name="aoi_reports"),
    "fi_reports": SupabaseTable(name="fi_reports"),
    "moat": SupabaseTable(
        name="moat",
        columns={"report_date": "Report Date"},
    ),
    "moat_dpm": SupabaseTable(
        name="moat_dpm",
        columns={"report_date": "Report Date"},
    ),
    "combined_reports": SupabaseTable(name="combined_reports"),
    "part_result_table": SupabaseTable(
        name="part_result_table",
        columns={"inspection_date": "inspection_date"},
    ),
    "defects": SupabaseTable(
        name="defects",
        columns={"id": "id", "name": "name"},
    ),
    "ppm_saved_queries": SupabaseTable(
        name="ppm_saved_queries",
        columns={
            "id": "id",
            "name": "name",
            "type": "type",
            "description": "description",
            "start_date": "start_date",
            "end_date": "end_date",
            "value_source": "value_source",
            "x_column": "x_column",
            "y_agg": "y_agg",
            "chart_type": "chart_type",
            "line_color": "line_color",
            "params": "params",
            "created_at": "created_at",
        },
    ),
    "dpm_saved_queries": SupabaseTable(
        name="dpm_saved_queries",
        columns={
            "id": "id",
            "name": "name",
            "type": "type",
            "description": "description",
            "start_date": "start_date",
            "end_date": "end_date",
            "value_source": "value_source",
            "x_column": "x_column",
            "y_agg": "y_agg",
            "chart_type": "chart_type",
            "line_color": "line_color",
            "params": "params",
            "created_at": "created_at",
        },
    ),
    "aoi_saved_queries": SupabaseTable(
        name="aoi_saved_queries",
        columns={
            "id": "id",
            "name": "name",
            "description": "description",
            "start_date": "start_date",
            "end_date": "end_date",
            "params": "params",
            "created_at": "created_at",
        },
    ),
    "fi_saved_queries": SupabaseTable(
        name="fi_saved_queries",
        columns={
            "id": "id",
            "name": "name",
            "description": "description",
            "start_date": "start_date",
            "end_date": "end_date",
            "params": "params",
            "created_at": "created_at",
        },
    ),
}


def table_name(identifier: str) -> str:
    """Return the configured Supabase table name for ``identifier``."""

    table = SUPABASE_SCHEMA.get(identifier)
    if table:
        return table.name
    return identifier


def column_name(table_identifier: str, column_identifier: str) -> str:
    """Return the configured column name for ``table_identifier``."""

    table = SUPABASE_SCHEMA.get(table_identifier)
    if table and column_identifier in table.columns:
        return table.columns[column_identifier]
    return column_identifier


def table_columns(table_identifier: str) -> Mapping[str, str]:
    """Return the configured column mapping for ``table_identifier``."""

    table = SUPABASE_SCHEMA.get(table_identifier)
    if table:
        return table.columns
    return {}


def to_supabase_payload(
    table_identifier: str, payload: Mapping[str, Any]
) -> Dict[str, Any]:
    """Return ``payload`` with keys mapped to Supabase column names."""

    columns = table_columns(table_identifier)
    if not columns:
        return dict(payload)
    return {columns.get(key, key): value for key, value in payload.items()}

