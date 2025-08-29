from flask import current_app
from datetime import datetime, timedelta


def _get_client():
    """Return the configured Supabase client."""
    return current_app.config["SUPABASE"]


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


def fetch_moat():
    """Retrieve MOAT data from the database."""
    supabase = _get_client()
    try:
        response = supabase.table("moat").select("*").execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch MOAT data: {exc}"


def fetch_recent_moat(days: int = 7):
    """Retrieve MOAT data for the past ``days`` days."""
    supabase = _get_client()
    start_date = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
    try:
        response = (
            supabase.table("moat")
            .select("*")
            .gte("Report Date", start_date)
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch recent MOAT data: {exc}"


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
