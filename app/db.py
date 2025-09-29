from datetime import date, datetime, timedelta, timezone
from collections import defaultdict
from typing import Any, Tuple

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


def fetch_app_versions() -> tuple[list[dict] | None, str | None]:
    """Return all recorded application release versions."""

    supabase, error = _ensure_supabase_client()
    if error:
        return [], error

    try:
        response = (
            supabase.table("app_versions")
            .select("*")
            .order("updated_at", desc=True)
            .execute()
        )
        return response.data or [], None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch app versions: {exc}"


def fetch_app_version(platform: str) -> tuple[dict | None, str | None]:
    """Return the release record for ``platform`` if available."""

    if not platform:
        return None, "Platform is required"

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    try:
        response = (
            supabase.table("app_versions")
            .select("*")
            .eq("platform", platform)
            .limit(1)
            .execute()
        )
        records = response.data or []
        return (records[0] if records else None), None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch app version: {exc}"


def upsert_app_version(
    platform: str,
    version: str,
    *,
    download_url: str | None = None,
    checksum: str | None = None,
    release_notes: str | None = None,
) -> tuple[list[dict] | None, str | None]:
    """Create or update a release entry for ``platform``."""

    if not platform:
        return None, "Platform is required"
    if not version:
        return None, "Version is required"

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    payload = {
        "platform": platform,
        "version": version,
        "download_url": download_url or None,
        "checksum": checksum or None,
        "release_notes": release_notes or None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        response = (
            supabase.table("app_versions")
            .upsert(payload, on_conflict="platform")
            .execute()
        )
        return response.data or [], None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to update app version: {exc}"


def fetch_feature_states() -> tuple[list[dict] | None, str | None]:
    """Return all persisted feature availability records."""

    supabase, error = _ensure_supabase_client()
    if error:
        return [], error

    try:
        response = supabase.table("app_feature_states").select("*").execute()
        return response.data or [], None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch feature states: {exc}"


def fetch_feature_state(slug: str) -> tuple[dict | None, str | None]:
    """Return the feature state identified by ``slug`` if it exists."""

    if not slug:
        return None, "Feature slug is required"

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    try:
        response = (
            supabase.table("app_feature_states")
            .select("*")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        records = response.data or []
        return (records[0] if records else None), None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch feature state: {exc}"


def upsert_feature_state(
    slug: str,
    *,
    status: str,
    message: str | None = None,
    bug_report_id: str | None = None,
) -> tuple[list[dict] | None, str | None]:
    """Create or update a feature state entry."""

    if not slug:
        return None, "Feature slug is required"
    if not status:
        return None, "Feature status is required"

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    bug_value: str | None
    if bug_report_id in (None, ""):
        bug_value = None
    else:
        bug_value = str(bug_report_id)

    payload = {
        "slug": slug,
        "status": status,
        "message": message or None,
        "bug_report_id": bug_value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        response = (
            supabase.table("app_feature_states")
            .upsert(payload, on_conflict="slug")
            .execute()
        )
        return response.data or [], None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to update feature state: {exc}"


def fetch_feature_states_for_bug(
    bug_report_id: str,
) -> tuple[list[dict] | None, str | None]:
    """Return feature state records associated with ``bug_report_id``."""

    if bug_report_id in (None, ""):
        return [], None

    supabase, error = _ensure_supabase_client()
    if error:
        return [], error

    try:
        response = (
            supabase.table("app_feature_states")
            .select("*")
            .eq("bug_report_id", str(bug_report_id))
            .execute()
        )
        return response.data or [], None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch linked feature states: {exc}"


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


def query_aoi_base_daily(
    sql: str, params: dict[str, object] | None = None
) -> tuple[dict[str, dict[str, list[dict]]] | None, str | None]:
    """Execute ``sql`` against ``aoi_base_daily`` and group the results.

    Args:
        sql: Parameterised SQL statement to execute. The query is expected to
            reference ``aoi_base_daily`` and return at least ``report_date`` and
            ``line`` columns so that results can be grouped for downstream
            aggregation.
        params: Optional mapping of parameters referenced by ``sql``.

    Returns:
        tuple: (grouped_rows, error). ``grouped_rows`` is a nested dictionary
        keyed first by ISO formatted ``report_date`` and then by ``line``. Each
        innermost value is a list of the original row dictionaries returned by
        Supabase. When the query fails ``grouped_rows`` will be ``None`` and
        ``error`` will contain an explanatory message.
    """

    if not sql or not sql.strip():
        return None, "SQL query is required"

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    params = params or {}

    try:
        rpc_payload = {"query": sql, "params": params}
        response = None

        if hasattr(supabase, "rpc") and callable(getattr(supabase, "rpc")):
            response = supabase.rpc("execute_sql", rpc_payload)
        elif hasattr(supabase, "postgrest") and hasattr(supabase.postgrest, "rpc"):
            response = supabase.postgrest.rpc("execute_sql", rpc_payload)
        else:  # pragma: no cover - unexpected client shape
            raise RuntimeError("Supabase client does not expose an RPC interface")

        data = getattr(response, "data", response) or []
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to execute AOI base daily query: {exc}"

    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for row in data:
        if not isinstance(row, dict):  # pragma: no cover - defensive guard
            continue
        raw_date = row.get("report_date") or row.get("Report Date")
        raw_line = row.get("line") or row.get("Line")

        if raw_date in (None, "") or raw_line in (None, ""):
            continue

        if isinstance(raw_date, datetime):
            date_key = raw_date.date().isoformat()
        elif isinstance(raw_date, date):
            date_key = raw_date.isoformat()
        else:
            date_key = str(raw_date)

        grouped[date_key][str(raw_line)].append(row)

    return grouped, None


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


def _normalize_date_for_query(value: date | datetime | str | None) -> str | None:
    """Return an ISO formatted date string for Supabase filters."""

    if not value:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _fetch_paginated_rows(
    table: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    order_column: str | None = None,
    page_size: int = 1000,
) -> list[dict]:
    """Fetch all rows from ``table`` applying optional range filters.

    Supabase caps responses to 1,000 rows by default.  This helper fetches data
    in ``page_size`` chunks while reapplying the requested range filters so that
    large exports do not truncate results.
    """

    if page_size <= 0:
        raise ValueError("page_size must be greater than zero")

    supabase = _get_client()
    rows: list[dict] = []
    offset = 0

    while True:
        query = supabase.table(table).select("*")
        if order_column:
            query = query.order(order_column)
        if start_date:
            query = query.gte("Report Date", start_date)
        if end_date:
            query = query.lte("Report Date", end_date)
        query = query.range(offset, offset + page_size - 1)

        response = query.execute()
        batch = response.data or []
        rows.extend(batch)

        if len(batch) < page_size:
            break
        offset += page_size

    return rows


def fetch_moat(
    start_date: date | datetime | str | None = None,
    end_date: date | datetime | str | None = None,
):
    """Retrieve MOAT data from the database.

    Optional ``start_date`` and ``end_date`` filters apply range constraints on
    ``Report Date``.  ``Report Date`` values are offset by -1 day to represent
    the original run date.
    """

    start_value = _normalize_date_for_query(start_date)
    end_value = _normalize_date_for_query(end_date)

    try:
        rows = _fetch_paginated_rows(
            "moat",
            start_date=start_value,
            end_date=end_value,
            order_column="Report Date",
        )
        data = _apply_report_date_offset(rows)
        return data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch MOAT data: {exc}"


def fetch_recent_moat(days: int = 7):
    """Retrieve MOAT data for the past ``days`` days.

    ``Report Date`` values are offset by -1 day to represent the original run
    date.
    """
    start_date = (datetime.utcnow() - timedelta(days=days)).date()
    return fetch_moat(start_date=start_date)


def fetch_moat_dpm(
    start_date: date | datetime | str | None = None,
    end_date: date | datetime | str | None = None,
):
    """Retrieve MOAT DPM data from the database."""

    start_value = _normalize_date_for_query(start_date)
    end_value = _normalize_date_for_query(end_date)

    try:
        rows = _fetch_paginated_rows(
            "moat_dpm",
            start_date=start_value,
            end_date=end_value,
            order_column="Report Date",
        )
        data = _apply_report_date_offset(rows)
        return data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch MOAT DPM data: {exc}"


def fetch_recent_moat_dpm(days: int = 7):
    """Retrieve recent MOAT DPM data for the past ``days`` days."""

    start_date = (datetime.utcnow() - timedelta(days=days)).date()
    return fetch_moat_dpm(start_date=start_date)


def fetch_defect_catalog() -> tuple[list[dict[str, str]] | None, str | None]:
    """Return the list of known defects with identifiers and names."""

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    try:
        response = supabase.table("defects").select("id,name").execute()
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
    """Return unique defect identifiers from the ``defects`` table."""

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


def insert_moat_dpm(data: dict):
    """Insert a single MOAT DPM record."""

    supabase = _get_client()
    try:
        response = supabase.table("moat_dpm").insert(data).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert MOAT DPM data: {exc}"


def insert_moat_dpm_bulk(rows: list[dict]):
    """Insert multiple MOAT DPM records."""

    supabase = _get_client()
    try:
        response = supabase.table("moat_dpm").insert(rows).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert MOAT DPM data: {exc}"


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


def fetch_dpm_saved_queries():
    """Retrieve saved chart queries for DPM analysis."""

    supabase = _get_client()
    try:
        response = (
            supabase.table("dpm_saved_queries")
            .select(
                "id,name,type,description,start_date,end_date,value_source,x_column,y_agg,"
                "chart_type,line_color,params,created_at"
            )
            .order("created_at", desc=True)
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch DPM saved queries: {exc}"


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


def insert_dpm_saved_query(data: dict):
    """Insert a saved DPM chart query definition into Supabase."""

    supabase = _get_client()
    try:
        response = supabase.table("dpm_saved_queries").insert(data).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to save DPM chart query: {exc}"


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


def update_dpm_saved_query(name: str, data: dict):
    """Update or upsert a saved DPM chart query definition by ``name``."""

    supabase = _get_client()
    try:
        payload = {**data, "name": name}
        response = (
            supabase.table("dpm_saved_queries")
            .upsert(payload, on_conflict="name")
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to update DPM saved query: {exc}"


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
