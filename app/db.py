from flask import current_app


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

