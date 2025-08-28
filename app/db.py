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


def fetch_saved_queries():
    """Retrieve saved chart queries for PPM analysis.

    Expects a Supabase table named 'ppm_saved_queries' with columns like:
      - id (uuid) [optional]
      - name (text)
      - type (text)
      - description (text)
      - params (json)
      - created_at (timestamptz)
    """
    supabase = _get_client()
    try:
        response = (
            supabase.table("ppm_saved_queries")
            .select("id,name,type,description,params,created_at")
            .order("created_at", desc=True)
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch saved queries: {exc}"


def insert_saved_query(data: dict):
    """Insert a saved chart query definition into Supabase.

    ``data`` should include ``name``, ``type``, ``params`` and optional ``description``.
    """
    supabase = _get_client()
    try:
        response = supabase.table("ppm_saved_queries").insert(data).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to save chart query: {exc}"


def update_saved_query(name: str, data: dict):
    """Update or upsert a saved chart query definition by ``name``.

    ``data`` may include ``type``, ``params`` and ``description`` which will be
    merged with the provided ``name``.
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
