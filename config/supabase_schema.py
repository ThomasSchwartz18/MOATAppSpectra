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

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class SupabaseTable:
    """Configuration for a Supabase table."""

    name: str
    columns: Mapping[str, str] = field(default_factory=dict)


# Default table and column mappings. These act as fallbacks if no environment
# overrides are supplied.
_DEFAULT_SUPABASE_SCHEMA: Dict[str, SupabaseTable] = {
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
    "aoi_reports": SupabaseTable(
        name="aoi_reports",
        columns={
            "id": "id",
            "date": "date",
            "shift": "shift",
            "operator_id": "operator_id",
            "customer_id": "customer_id",
            "rev": "rev",
            "assembly_id": "assembly_id",
            "job_number": "job_number",
            "quantity_inspected": "quantity_inspected",
            "quantity_rejected": "quantity_rejected",
            "additional_information": "additional_information",
            "program": "program",
        },
    ),
    "fi_reports": SupabaseTable(
        name="fi_reports",
        columns={
            "id": "id",
            "date": "date",
            "shift": "shift",
            "operator_id": "operator_id",
            "customer_id": "customer_id",
            "rev": "rev",
            "assembly_id": "assembly_id",
            "job_number": "job_number",
            "quantity_inspected": "quantity_inspected",
            "quantity_rejected": "quantity_rejected",
            "additional_information": "additional_information",
        },
    ),
    "moat": SupabaseTable(
        name="ppm_moat",
        columns={
            "id": "id",
            "total_boards": "total_boards",
            "total_parts_per_board": "total_parts_per_board",
            "total_parts": "total_parts",
            "ng_parts": "ng_parts",
            "ng_ppm": "ng_ppm",
            "falsecall_parts": "falsecall_parts",
            "falsecall_ppm": "falsecall_ppm",
            "report_date": "report_date",
            "line": "line",
            "model_name": "model_name",
            "created_at": "created_at",
        },
    ),
    "moat_dpm": SupabaseTable(
        name="dpm_moat",
        columns={
            "id": "id",
            "created_at": "created_at",
            "report_date": "report_date",
            "total_boards": "total_boards",
            "windows_per_board": "windows_per_board",
            "total_windows": "total_windows",
            "ng_windows": "ng_windows",
            "dpm": "dpm",
            "falsecall_windows": "falsecall_windows",
            "fc_dpm": "fc_dpm",
            "model_name": "model_name",
            "line": "line",
        },
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
    "customers": SupabaseTable(
        name="customer",
        columns={
            "id": "id",
            "created_at": "created_at",
            "name": "name",
            "manager": "manager",
            "alt_names": "alt_names",
        },
    ),
    "assemblies": SupabaseTable(
        name="assembly",
        columns={
            "id": "id",
            "customer_id": "customer_id",
            "assembly_no": "assembly_no",
            "rev": "rev",
            "assembly_id": "assembly_id",
        },
    ),
    "jobs": SupabaseTable(
        name="job",
        columns={
            "id": "id",
            "job_number": "job_number",
            "customer_id": "customer_id",
            "assembly_id": "assembly_id",
            "start_date": "start_date",
            "end_date": "end_date",
            "panel_count": "panel_count",
            "last_operation_completed": "last_operation_completed",
            "operations": "operations",
            "additional_information": "additional_information",
            "created_at": "created_at",
            "updated_at": "updated_at",
            "assembly_color_id": "assembly_color_id",
        },
    ),
    "operators": SupabaseTable(
        name="operator",
        columns={
            "id": "id",
            "name": "name",
            "role": "role",
        },
    ),
}


def _normalise_columns(columns: Any) -> Dict[str, str]:
    """Return a string-to-string column mapping from ``columns``."""

    if not isinstance(columns, Mapping):
        return {}
    return {
        str(logical): str(actual)
        for logical, actual in columns.items()
        if isinstance(logical, str) and isinstance(actual, str)
    }


def _load_schema_from_env() -> Dict[str, SupabaseTable]:
    """Build the Supabase schema from environment overrides."""

    schema = dict(_DEFAULT_SUPABASE_SCHEMA)

    raw_schema = os.getenv("SUPABASE_SCHEMA_JSON")
    if not raw_schema:
        return schema

    try:
        parsed = json.loads(raw_schema)
    except json.JSONDecodeError:
        return schema

    if not isinstance(parsed, Mapping):
        return schema

    for identifier, entry in parsed.items():
        if not isinstance(identifier, str) or not isinstance(entry, Mapping):
            continue

        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue

        columns = _normalise_columns(entry.get("columns", {}))
        schema[identifier] = SupabaseTable(name=name, columns=columns)

    return schema


SUPABASE_SCHEMA: Dict[str, SupabaseTable] = _load_schema_from_env()


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
