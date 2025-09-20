from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Tuple

from flask import current_app


def _get_client():
    """Return the configured Supabase client."""
    return current_app.config["SUPABASE"]


def _ensure_supabase_client() -> Tuple[Any, str | None]:
    """Return the configured Supabase client or an explanatory error.

    Returns:
        tuple: (client, error). When Supabase is unavailable the client will be
        ``None`` and ``error`` will contain a message explaining the failure.
    """

    supabase = current_app.config.get("SUPABASE")
    if not supabase or not hasattr(supabase, "table"):
        return None, (
            "Supabase client is not configured. Set SUPABASE_URL and SUPABASE_"
            "SERVICE_KEY to enable database-backed user management."
        )
    return supabase, None


def _apply_report_date_offset(rows: list[dict]) -> list[dict]:
    """Subtract one day from any MOAT ``Report Date`` fields.

    MOAT data currently stores ``Report Date`` one day ahead of the actual run
    date.  This temporary workaround presents the original run date until the
    historical records are corrected.  Remove this helper once the upstream data
    is fixed.
    """
    offset = timedelta(days=1)
    for row in rows or []:
        for key in ("Report Date", "report_date"):
            val = row.get(key)
            if not val:
                continue
            try:
                dt = datetime.fromisoformat(str(val)) - offset
                row[key] = dt.date().isoformat()
            except Exception:  # pragma: no cover - parsing errors
                continue
    return rows


def fetch_app_users(include_sensitive: bool = False) -> tuple[list[dict] | None, str | None]:
    """Return application users stored in Supabase.

    Args:
        include_sensitive: When ``True`` the returned records include sensitive
            fields such as ``password_hash``.  Callers must take care not to
            expose these values.

    Returns:
        tuple[list | None, str | None]: The list of user dictionaries or an
        error message if the query failed.
    """

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    try:
        response = supabase.table("app_users").select("*").execute()
        data = response.data or []
        if not include_sensitive:
            sanitized: list[dict] = []
            for row in data:
                sanitized.append(
                    {key: value for key, value in row.items() if key != "password_hash"}
                )
            data = sanitized
        return data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch app users: {exc}"


def fetch_app_user_credentials(username: str) -> tuple[dict | None, str | None]:
    """Return the Supabase record for ``username`` if it exists."""

    records, error = fetch_app_users(include_sensitive=True)
    if error:
        return None, error

    normalized = (username or "").casefold()
    for record in records or []:
        if (record.get("username") or "").casefold() == normalized:
            return record, None
    return None, None


def insert_app_user(record: dict) -> tuple[list[dict] | None, str | None]:
    """Insert a new user into the ``app_users`` table."""

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    try:
        response = supabase.table("app_users").insert(record).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to create user: {exc}"


def insert_bug_report(record: dict) -> tuple[list[dict] | None, str | None]:
    """Insert a bug report into the ``bug_reports`` table."""

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    payload = dict(record)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    attachments = payload.get("attachments")
    if attachments is not None and not isinstance(attachments, list):
        payload["attachments"] = list(attachments)

    try:
        response = supabase.table("bug_reports").insert(payload).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to create bug report: {exc}"


def delete_app_user(user_id: str) -> tuple[list[dict] | None, str | None]:
    """Delete the Supabase user identified by ``user_id``."""

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    try:
        response = supabase.table("app_users").delete().eq("id", user_id).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to delete user: {exc}"


def fetch_bug_reports(
    filters: dict[str, Any] | None = None,
) -> tuple[list[dict] | None, str | None]:
    """Return bug reports optionally filtered by column equality."""

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    try:
        query = supabase.table("bug_reports").select("*")
        filters = filters or {}
        for key, value in filters.items():
            if value is None:
                continue
            query = query.eq(key, value)
        response = query.order("created_at", desc=True).execute()
        return response.data or [], None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch bug reports: {exc}"


def update_bug_report_status(
    report_id: int | str,
    updates: dict[str, Any],
) -> tuple[list[dict] | None, str | None]:
    """Update the status or metadata of a bug report."""

    if not updates:
        return None, "No updates supplied"

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    payload = dict(updates)
    attachments: Iterable[str] | None = payload.get("attachments")
    if attachments is not None and not isinstance(attachments, list):
        payload["attachments"] = list(attachments)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        response = (
            supabase.table("bug_reports")
            .update(payload)
            .eq("id", report_id)
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to update bug report: {exc}"


def fetch_aoi_reports():
    """Retrieve all AOI reports from the database.

    Returns:
        tuple[list | None, str | None]: (data, error)
    """
    supabase = _get_client()
    try:
        response = supabase.table("aoi_reports").select("*").execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch AOI reports: {exc}"


def fetch_fi_reports():
    """Retrieve all FI reports from the database."""
    supabase = _get_client()
    try:
        response = supabase.table("fi_reports").select("*").execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch FI reports: {exc}"


def fetch_combined_reports():
    """Retrieve all combined reports from the database.

    Returns:
        tuple[list | None, str | None]: (data, error)
    """
    supabase = _get_client()
    try:
        response = supabase.table("combined_reports").select("*").execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch combined reports: {exc}"


def fetch_moat():
    """Retrieve MOAT data from the database.

    ``Report Date`` values are offset by -1 day to represent the original run
    date.
    """
    supabase = _get_client()
    try:
        response = supabase.table("moat").select("*").execute()
        data = _apply_report_date_offset(response.data)
        return data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch MOAT data: {exc}"


def fetch_recent_moat(days: int = 7):
    """Retrieve MOAT data for the past ``days`` days.

    ``Report Date`` values are offset by -1 day to represent the original run
    date.
    """
    supabase = _get_client()
    start_date = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
    try:
        response = (
            supabase.table("moat")
            .select("*")
            .gte("Report Date", start_date)
            .execute()
        )
        data = _apply_report_date_offset(response.data)
        return data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch recent MOAT data: {exc}"


def fetch_defect_catalog() -> tuple[list[dict[str, str]] | None, str | None]:
    """Return the list of known defects with identifiers and names."""

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    try:
        response = supabase.table("defect").select("id,name").execute()
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch defects: {exc}"

    catalog: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in response.data or []:
        raw_id = row.get("id")
        raw_name = row.get("name")
        defect_id = str(raw_id).strip() if raw_id is not None else ""
        defect_name = str(raw_name).strip() if raw_name is not None else ""
        if not defect_id:
            continue
        normalized = defect_id.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        catalog.append({"id": defect_id, "name": defect_name})

    catalog.sort(key=lambda item: item["id"].lower())
    return catalog, None


def fetch_distinct_defect_ids() -> tuple[list[str] | None, str | None]:
    """Return unique defect identifiers from the ``defect`` table."""

    catalog, error = fetch_defect_catalog()
    if error:
        return None, error

    identifiers = [item["id"] for item in catalog or []]
    return identifiers, None


def insert_aoi_report(data: dict):
    """Insert a new AOI report.

    Args:
        data (dict): Data representing the AOI report.
    """
    supabase = _get_client()
    try:
        response = supabase.table("aoi_reports").insert(data).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert AOI report: {exc}"


def insert_aoi_reports_bulk(rows: list[dict]):
    """Insert multiple AOI reports at once.

    Args:
        rows (list[dict]): List of AOI report dictionaries.
    """
    supabase = _get_client()
    try:
        response = supabase.table("aoi_reports").insert(rows).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert AOI reports: {exc}"


def insert_fi_report(data: dict):
    """Insert a new FI report."""
    supabase = _get_client()
    try:
        response = supabase.table("fi_reports").insert(data).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert FI report: {exc}"


def insert_moat(data: dict):
    """Insert MOAT data."""
    supabase = _get_client()
    try:
        response = supabase.table("moat").insert(data).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert MOAT data: {exc}"


def insert_moat_bulk(rows: list[dict]):
    """Insert multiple MOAT records at once."""
    supabase = _get_client()
    try:
        response = supabase.table("moat").insert(rows).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert MOAT data: {exc}"


def fetch_saved_queries():
    """Retrieve saved chart queries for PPM analysis.

    Expects a Supabase table named 'ppm_saved_queries' with columns like:
      - id (uuid) [optional]
      - name (text)
      - type (text)
      - description (text)
      - start_date (date)
      - end_date (date)
      - value_source (text)
      - x_column (text)
      - y_agg (text)
      - chart_type (text)
      - line_color (text)
      - params (json)
      - created_at (timestamptz)
    """
    supabase = _get_client()
    try:
        response = (
            supabase.table("ppm_saved_queries")
            .select(
                "id,name,type,description,start_date,end_date,value_source,x_column,y_agg,"
                "chart_type,line_color,params,created_at"
            )
            .order("created_at", desc=True)
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch saved queries: {exc}"


def insert_saved_query(data: dict):
    """Insert a saved chart query definition into Supabase.

    ``data`` should include ``name``, ``type`` and ``params`` along with optional
    fields like ``description``, ``start_date``, ``end_date``, ``value_source``,
    ``x_column``, ``y_agg``, ``chart_type`` and ``line_color``.
    """
    supabase = _get_client()
    try:
        response = supabase.table("ppm_saved_queries").insert(data).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to save chart query: {exc}"


def update_saved_query(name: str, data: dict):
    """Update or upsert a saved chart query definition by ``name``.

    ``data`` may include ``type``, ``params`` and any of the optional metadata
    fields (``description``, ``start_date``, ``end_date``, ``value_source``,
    ``x_column``, ``y_agg``, ``chart_type``, ``line_color``) which will be merged
    with the provided ``name``.
    """
    supabase = _get_client()
    try:
        payload = {**data, "name": name}
        response = (
            supabase.table("ppm_saved_queries")
            .upsert(payload, on_conflict="name")
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to update saved query: {exc}"


def fetch_saved_aoi_queries():
    """Retrieve saved chart queries for the AOI Daily Reports page.

    Expects a Supabase table named ``aoi_saved_queries`` with at least the
    following columns:
      - id (uuid) [optional]
      - name (text)
      - description (text)
      - start_date (date)
      - end_date (date)
      - params (json)
      - created_at (timestamptz)
    """
    supabase = _get_client()
    try:
        response = (
            supabase.table("aoi_saved_queries")
            .select("id,name,description,start_date,end_date,params,created_at")
            .order("created_at", desc=True)
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch AOI saved queries: {exc}"


def insert_saved_aoi_query(data: dict):
    """Insert a saved AOI chart query definition into Supabase."""
    supabase = _get_client()
    try:
        response = supabase.table("aoi_saved_queries").insert(data).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to save AOI chart query: {exc}"


def update_saved_aoi_query(name: str, data: dict):
    """Update or upsert a saved AOI chart query by ``name``."""
    supabase = _get_client()
    try:
        payload = {**data, "name": name}
        response = (
            supabase.table("aoi_saved_queries")
            .upsert(payload, on_conflict="name")
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to update AOI saved query: {exc}"


def fetch_saved_fi_queries():
    """Retrieve saved chart queries for the FI Daily Reports page."""
    supabase = _get_client()
    try:
        response = (
            supabase.table("fi_saved_queries")
            .select("id,name,description,start_date,end_date,params,created_at")
            .order("created_at", desc=True)
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch FI saved queries: {exc}"


def insert_saved_fi_query(data: dict):
    """Insert a saved FI chart query definition into Supabase."""
    supabase = _get_client()
    try:
        response = supabase.table("fi_saved_queries").insert(data).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to save FI chart query: {exc}"


def update_saved_fi_query(name: str, data: dict):
    """Update or upsert a saved FI chart query by ``name``."""
    supabase = _get_client()
    try:
        payload = {**data, "name": name}
        response = (
            supabase.table("fi_saved_queries")
            .upsert(payload, on_conflict="name")
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to update FI saved query: {exc}"
