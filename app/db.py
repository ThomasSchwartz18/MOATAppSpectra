from datetime import date, datetime, timedelta, timezone
from collections import defaultdict
from typing import Any, Tuple
import math

from flask import current_app

from config.supabase_schema import column_name, table_name, to_supabase_payload


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


def _safe_number(value):
    """Return ``value`` as a float when possible, otherwise ``None``."""

    if value is None:
        return None

    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(number) or math.isinf(number):
            return None
        return number

    text = str(value).strip()
    if not text:
        return None

    text = text.replace(",", "")
    if text.endswith("%"):
        text = text[:-1]

    try:
        number = float(text)
    except (TypeError, ValueError):
        return None

    if math.isnan(number) or math.isinf(number):
        return None

    return number


def _normalize_ppm_row(row: dict) -> dict:
    """Augment MOAT PPM rows with canonical field names."""

    if not isinstance(row, dict):
        return row

    def pick(*names):
        for name in names:
            if name in row:
                value = row.get(name)
                if value not in (None, ""):
                    return value
        return None

    def assign_numeric(target: str, *names: str) -> None:
        if target in row:
            return
        raw = pick(*names)
        number = _safe_number(raw)
        if number is not None:
            row[target] = number

    assign_numeric("boards_in", "boards_in", "Boards In", "Total Boards", "total_boards")
    assign_numeric("boards_out", "boards_out", "Boards Out", "Good Boards", "good_boards")
    assign_numeric("boards_ng", "boards_ng", "Boards NG", "NG Boards", "boards_ng")
    assign_numeric("units_in", "units_in", "Units In", "total_units", "Total Units")
    assign_numeric("units_out", "units_out", "Units Out", "Good Units")
    assign_numeric("units_ng", "units_ng", "Units NG", "NG Units")
    assign_numeric("parts_total", "parts_total", "Parts Total", "Total Parts", "total_parts")
    assign_numeric("ok_parts", "ok_parts", "OK Parts", "Good Parts", "ok_parts")
    assign_numeric(
        "ng_parts_true",
        "ng_parts_true",
        "True Defect Parts",
        "NG Parts",
        "ng_parts",
    )
    assign_numeric("fc_parts", "fc_parts", "FalseCall Parts", "falsecall_parts", "FC Parts")
    assign_numeric("true_defect_ppm", "true_defect_ppm", "NG PPM", "true_ppm", "ng_ppm")
    assign_numeric(
        "false_call_ppm",
        "false_call_ppm",
        "FalseCall PPM",
        "fc_ppm",
    )

    if "first_pass_yield" not in row:
        raw = pick("first_pass_yield", "First Pass Yield", "first_pass_yield_parts")
        number = _safe_number(raw)
        if number is None:
            total = _safe_number(row.get("parts_total"))
            ok_parts = _safe_number(row.get("ok_parts"))
            if ok_parts is None and total is not None:
                ng_parts = _safe_number(row.get("ng_parts_true")) or 0.0
                fc_parts = _safe_number(row.get("fc_parts")) or 0.0
                residual = total - ng_parts - fc_parts
                ok_parts = residual if residual >= 0 else None
            if ok_parts is not None and total not in (None, 0):
                number = ok_parts / total
        if number is not None:
            row["first_pass_yield"] = number

    return row


def _normalize_dpm_row(row: dict) -> dict:
    """Augment MOAT DPM rows with canonical field names."""

    if not isinstance(row, dict):
        return row

    def pick(*names):
        for name in names:
            if name in row:
                value = row.get(name)
                if value not in (None, ""):
                    return value
        return None

    def assign_numeric(target: str, *names: str) -> None:
        if target in row:
            return
        raw = pick(*names)
        number = _safe_number(raw)
        if number is not None:
            row[target] = number

    def assign_text(target: str, *names: str) -> None:
        if target in row:
            return
        raw = pick(*names)
        if raw is not None:
            row[target] = raw

    assign_numeric(
        "opportunities_total",
        "opportunities_total",
        "Total Windows",
        "total_windows",
        "Opportunities Total",
    )
    assign_numeric(
        "defect_count_true",
        "defect_count_true",
        "True Defect Count",
        "NG Windows",
        "ng_windows",
    )
    assign_numeric(
        "false_call_count",
        "false_call_count",
        "FalseCall Windows",
        "falsecall_windows",
        "False Call Count",
    )
    assign_numeric("windows_per_board", "windows_per_board", "Windows per board")
    assign_numeric("boards_total", "boards_total", "Total Boards", "total_boards", "Boards")
    assign_numeric("dpm", "dpm", "DPM")
    assign_numeric("fc_dpm", "fc_dpm", "FC DPM", "false_call_dpm")

    assign_text("defect_code", "defect_code", "Defect Code", "ng_code")
    assign_text("defect_class", "defect_class", "Defect Class")
    assign_text("inspector_type", "inspector_type", "Inspector Type")

    if row.get("dpm") is None:
        defects = _safe_number(row.get("defect_count_true"))
        opportunities = _safe_number(row.get("opportunities_total"))
        if opportunities not in (None, 0) and defects is not None:
            row["dpm"] = (defects / opportunities) * 1_000_000

    if row.get("fc_dpm") is None:
        fc = _safe_number(row.get("false_call_count"))
        opportunities = _safe_number(row.get("opportunities_total"))
        if opportunities not in (None, 0) and fc is not None:
            row["fc_dpm"] = (fc / opportunities) * 1_000_000

    return row


_AOI_REPORT_ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "date": ("Date", "aoi_Date"),
    "shift": ("Shift", "aoi_Shift"),
    "operator": ("Operator", "aoi_Operator"),
    "customer": ("Customer", "aoi_Customer"),
    "assembly": ("Assembly", "aoi_Assembly"),
    "rev": ("Rev", "aoi_Rev"),
    "job_number": ("Job Number", "aoi_Job Number"),
    "quantity_inspected": ("Quantity Inspected", "aoi_Quantity Inspected"),
    "quantity_rejected": ("Quantity Rejected", "aoi_Quantity Rejected"),
    "additional_information": ("Additional Information", "aoi_Additional Information"),
    "program": ("Program", "aoi_Program"),
    "id": ("aoi_ID",),
}


_FI_REPORT_ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "date": ("Date", "fi_Date"),
    "shift": ("Shift", "fi_Shift"),
    "operator": ("Operator", "fi_Operator"),
    "customer": ("Customer", "fi_Customer"),
    "assembly": ("Assembly", "fi_Assembly"),
    "rev": ("Rev", "fi_Rev"),
    "job_number": ("Job Number", "fi_Job Number"),
    "quantity_inspected": ("Quantity Inspected", "fi_Quantity Inspected"),
    "quantity_rejected": ("Quantity Rejected", "fi_Quantity Rejected"),
    "additional_information": ("Additional Information", "fi_Additional Information"),
    "id": ("fi_ID",),
}


_COMBINED_ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "aoi_date": ("aoi_Date", "Date"),
    "fi_date": ("fi_Date",),
    "aoi_qty_inspected": ("aoi_Quantity Inspected", "Quantity Inspected"),
    "aoi_qty_rejected": ("aoi_Quantity Rejected", "Quantity Rejected"),
    "fi_qty_inspected": ("fi_Quantity Inspected",),
    "fi_qty_rejected": ("fi_Quantity Rejected",),
    "aoi_customer": ("aoi_Customer", "Customer"),
    "aoi_additional_information": ("aoi_Additional Information",),
    "fi_operator": ("fi_Operator",),
    "fi_customer": ("fi_Customer",),
    "fi_assembly": ("fi_Assembly",),
    "fi_rev": ("fi_Rev",),
    "fi_additional_information": ("fi_Additional Information",),
    "aoi_assembly": ("aoi_Assembly", "Assembly"),
    "aoi_rev": ("aoi_Rev", "Rev"),
    "job_number": ("aoi_Job Number", "Job Number"),
    "fi_shift": ("fi_Shift",),
    "aoi_program": ("aoi_Program", "Program"),
    "aoi_shift": ("aoi_Shift", "Shift"),
    "aoi_operator": ("aoi_Operator", "Operator"),
    "aoi_station": ("aoi_Station", "Station"),
    "fi_part_type": ("fi_Part Type",),
    "days_from_aoi_to_fi": ("Days From AOI to FI",),
    "aoi_id": ("aoi_ID",),
    "fi_id": ("fi_ID",),
    "has_fi": ("has_fi",),
}


def _apply_aliases(rows: list[dict], mapping: dict[str, tuple[str, ...]]) -> list[dict]:
    """Populate legacy keys expected by analytics from modern snake_case data."""

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for source, targets in mapping.items():
            if source not in row:
                continue
            value = row[source]
            for target in targets:
                row.setdefault(target, value)
    return rows


def _apply_aoi_aliases(rows: list[dict]) -> list[dict]:
    return _apply_aliases(rows, _AOI_REPORT_ALIAS_MAP)


def _apply_fi_aliases(rows: list[dict]) -> list[dict]:
    return _apply_aliases(rows, _FI_REPORT_ALIAS_MAP)


def _apply_combined_aliases(rows: list[dict]) -> list[dict]:
    return _apply_aliases(rows, _COMBINED_ALIAS_MAP)


def ensure_customer(name: str) -> tuple[int | None, str | None]:
    """Return the customer id for ``name``; create the row when missing."""

    normalized = (name or '').strip()
    if not normalized:
        return None, "Customer name is required."

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    table = table_name("customers")
    id_column = column_name("customers", "id")
    name_column = column_name("customers", "name")
    alt_column = column_name("customers", "alt_names")

    def _lookup_existing() -> tuple[dict | None, str | None]:
        try:
            response = (
                supabase.table(table)
                .select(f"{id_column},{alt_column}")
                .eq(name_column, normalized)
                .limit(1)
                .execute()
            )
        except Exception as exc:  # pragma: no cover - network errors
            return None, f"Failed to lookup customer: {exc}"

        rows = getattr(response, "data", None) or []
        if rows:
            return rows[0], None

        try:
            response = (
                supabase.table(table)
                .select(f"{id_column},{alt_column}")
                .ilike(name_column, normalized)
                .limit(1)
                .execute()
            )
        except Exception as exc:  # pragma: no cover - network errors
            return None, f"Failed to lookup customer: {exc}"

        rows = getattr(response, "data", None) or []
        if rows:
            return rows[0], None

        try:
            response = supabase.table(table).select(f"{id_column},{alt_column}").execute()
        except Exception as exc:  # pragma: no cover - network errors
            return None, f"Failed to lookup customer: {exc}"

        for row in getattr(response, "data", None) or []:
            alt_names = row.get(alt_column) or []
            if not isinstance(alt_names, list):
                continue
            alt_lower = {alt.strip().lower() for alt in alt_names if isinstance(alt, str)}
            if normalized.lower() in alt_lower:
                return row, None
        return None, None

    existing_row, lookup_error = _lookup_existing()
    if lookup_error:
        return None, lookup_error

    if existing_row:
        alt_names = existing_row.get(alt_column) or []
        if isinstance(alt_names, list):
            alt_lower = {alt.strip().lower() for alt in alt_names if isinstance(alt, str)}
            if normalized.lower() not in alt_lower:
                updated_alt_names = alt_names + [normalized]
                try:
                    supabase.table(table).update({alt_column: updated_alt_names}).eq(id_column, existing_row.get(id_column)).execute()
                except Exception:  # pragma: no cover - ignore update failure
                    pass
        return existing_row.get(id_column), None

    insert_payload = {
        name_column: normalized,
        alt_column: [normalized],
    }
    try:
        insert_response = (
            supabase.table(table)
            .insert(insert_payload)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - network errors
        err_args = getattr(exc, "args", [])
        for entry in err_args or []:
            if isinstance(entry, dict) and entry.get("code") == "23505":
                existing_row, lookup_error = _lookup_existing()
                if lookup_error:
                    return None, lookup_error
                if existing_row:
                    return existing_row.get(id_column), None
        return None, f"Failed to create customer record: {exc}"

    inserted = getattr(insert_response, "data", None) or []
    if not inserted:
        return None, "Failed to create customer record."
    return inserted[0].get(id_column), None


def ensure_customer_assembly(customer_id: int, assembly_no: str, rev: str | None) -> tuple[int | None, str | None]:
    """Return the assembly id for ``assembly_no``/``rev`` creating/updating as required."""

    if not isinstance(customer_id, int):
        return None, "Customer id must be an integer."

    assembly_value = (assembly_no or '').strip()
    if not assembly_value:
        return None, "Assembly number is required."

    rev_value = (rev or '').strip()

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    table = table_name("assemblies")
    id_column = column_name("assemblies", "id")
    customer_column = column_name("assemblies", "customer_id")
    assembly_column = column_name("assemblies", "assembly_no")
    rev_column = column_name("assemblies", "rev")

    try:
        response = (
            supabase.table(table)
            .select(f"{id_column},{assembly_column},{rev_column}")
            .eq(customer_column, customer_id)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to lookup assembly: {exc}"

    rows = []
    for row in getattr(response, "data", None) or []:
        existing_assembly = (row.get(assembly_column) or '').strip()
        if existing_assembly.lower() == assembly_value.lower():
            rows.append(row)

    def _update_rev(row: dict, new_rev: str) -> tuple[int | None, str | None]:
        try:
            supabase.table(table).update({rev_column: new_rev}).eq(id_column, row.get(id_column)).execute()
        except Exception as exc:  # pragma: no cover - network errors
            return None, f"Failed to update assembly revision: {exc}"
        row[rev_column] = new_rev
        return row.get(id_column), None

    if rev_value:
        for row in rows:
            existing_rev = (row.get(rev_column) or '').strip()
            if existing_rev and existing_rev.lower() == rev_value.lower():
                return row.get(id_column), None
        for row in rows:
            existing_rev = (row.get(rev_column) or '').strip()
            if not existing_rev:
                return _update_rev(row, rev_value)
        insert_payload = {
            customer_column: customer_id,
            assembly_column: assembly_value,
            rev_column: rev_value,
        }
        try:
            insert_response = (
                supabase.table(table)
                .insert(insert_payload)
                .execute()
            )
        except Exception as exc:  # pragma: no cover - network errors
            return None, f"Failed to create assembly record: {exc}"
        inserted = getattr(insert_response, "data", None) or []
        if not inserted:
            return None, "Failed to create assembly record."
        return inserted[0].get(id_column), None

    # No revision specified yet.
    if rows:
        for row in rows:
            existing_rev = (row.get(rev_column) or '').strip()
            if not existing_rev:
                return row.get(id_column), None
        return rows[0].get(id_column), None

    insert_payload = {
        customer_column: customer_id,
        assembly_column: assembly_value,
        rev_column: None,
    }
    try:
        insert_response = (
            supabase.table(table)
            .insert(insert_payload)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to create assembly record: {exc}"

    inserted = getattr(insert_response, "data", None) or []
    if not inserted:
        return None, "Failed to create assembly record."
    return inserted[0].get(id_column), None


def ensure_operator(name: str, role: str | None) -> tuple[int | None, str | None]:
    """Ensure ``name`` exists in the operator table, appending ``role`` when provided."""

    normalized_name = (name or "").strip()
    if not normalized_name:
        return None, "Operator name is required."

    role_value = (role or "").strip()

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    table = table_name("operators")
    id_column = column_name("operators", "id")
    name_column = column_name("operators", "name")
    role_column = column_name("operators", "role")

    def _lookup_existing() -> tuple[dict | None, str | None]:
        try:
            response = supabase.table(table).select(f"{id_column},{name_column},{role_column}").execute()
        except Exception as exc:  # pragma: no cover - network errors
            return None, f"Failed to lookup operator: {exc}"
        for row in getattr(response, "data", None) or []:
            existing_name = (row.get(name_column) or "").strip()
            if existing_name.lower() == normalized_name.lower():
                return row, None
        return None, None

    existing_row, lookup_error = _lookup_existing()
    if lookup_error:
        return None, lookup_error

    if existing_row:
        existing_roles = (existing_row.get(role_column) or "").strip()
        if role_value:
            role_parts = [part.strip() for part in existing_roles.split(",") if part.strip()]
            role_lower = {part.lower() for part in role_parts}
            if role_value.lower() not in role_lower:
                role_parts.append(role_value)
                updated_roles = ", ".join(role_parts)
                try:
                    supabase.table(table).update({role_column: updated_roles}).eq(id_column, existing_row.get(id_column)).execute()
                except Exception as exc:  # pragma: no cover - network errors
                    return None, f"Failed to update operator role: {exc}"
        return existing_row.get(id_column), None

    insert_payload = {
        name_column: normalized_name,
        role_column: role_value or None,
    }
    try:
        insert_response = supabase.table(table).insert(insert_payload).execute()
    except Exception as exc:  # pragma: no cover - network errors
        err_args = getattr(exc, "args", [])
        for entry in err_args or []:
            if isinstance(entry, dict) and entry.get("code") == "23505":
                existing_row, lookup_error = _lookup_existing()
                if lookup_error:
                    return None, lookup_error
                if existing_row:
                    return existing_row.get(id_column), None
        return None, f"Failed to create operator record: {exc}"

    inserted = getattr(insert_response, "data", None) or []
    if not inserted:
        return None, "Failed to create operator record."
    return inserted[0].get(id_column), None


def ensure_job(
    job_number: str,
    *,
    customer_id: int | None = None,
    assembly_id: int | None = None,
) -> tuple[int | None, str | None]:
    """Ensure a ``job`` row exists for ``job_number`` with optional associations."""

    normalized = (job_number or "").strip()
    if not normalized:
        return None, "Job number is required."

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    table = table_name("jobs")
    id_column = column_name("jobs", "id")
    job_number_column = column_name("jobs", "job_number")
    customer_column = column_name("jobs", "customer_id")
    assembly_column = column_name("jobs", "assembly_id")

    try:
        response = (
            supabase.table(table)
            .select(f"{id_column},{customer_column},{assembly_column}")
            .eq(job_number_column, normalized)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to lookup job: {exc}"

    rows = getattr(response, "data", None) or []
    if rows:
        return rows[0].get(id_column), None

    payload = {
        job_number_column: normalized,
    }
    if isinstance(customer_id, int):
        payload[customer_column] = customer_id
    if isinstance(assembly_id, int):
        payload[assembly_column] = assembly_id

    try:
        insert_response = supabase.table(table).insert(payload).execute()
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to create job record: {exc}"

    inserted = getattr(insert_response, "data", None) or []
    if not inserted:
        return None, "Failed to create job record."
    return inserted[0].get(id_column), None


def fetch_app_versions() -> tuple[list[dict] | None, str | None]:
    """Return all recorded application release versions."""

    supabase, error = _ensure_supabase_client()
    if error:
        return [], error

    try:
        response = (
            supabase.table(table_name("app_versions"))
            .select("*")
            .order(column_name("app_versions", "updated_at"), desc=True)
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
            supabase.table(table_name("app_versions"))
            .select("*")
            .eq(column_name("app_versions", "platform"), platform)
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
    payload = to_supabase_payload("app_versions", payload)

    try:
        response = (
            supabase.table(table_name("app_versions"))
            .upsert(payload, on_conflict=column_name("app_versions", "platform"))
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
        response = (
            supabase.table(table_name("app_feature_states"))
            .select("*")
            .execute()
        )
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
            supabase.table(table_name("app_feature_states"))
            .select("*")
            .eq(column_name("app_feature_states", "slug"), slug)
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
    payload = to_supabase_payload("app_feature_states", payload)

    try:
        response = (
            supabase.table(table_name("app_feature_states"))
            .upsert(
                payload,
                on_conflict=column_name("app_feature_states", "slug"),
            )
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
            supabase.table(table_name("app_feature_states"))
            .select("*")
            .eq(
                column_name("app_feature_states", "bug_report_id"),
                str(bug_report_id),
            )
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
        response = supabase.table(table_name("app_users")).select("*").execute()
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
        payload = to_supabase_payload("app_users", record)
        response = supabase.table(table_name("app_users")).insert(payload).execute()
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
    payload = to_supabase_payload("bug_reports", payload)

    try:
        response = supabase.table(table_name("bug_reports")).insert(payload).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to create bug report: {exc}"


def delete_app_user(user_id: str) -> tuple[list[dict] | None, str | None]:
    """Delete the Supabase user identified by ``user_id``."""

    supabase, error = _ensure_supabase_client()
    if error:
        return None, error

    try:
        response = (
            supabase.table(table_name("app_users"))
            .delete()
            .eq(column_name("app_users", "id"), user_id)
            .execute()
        )
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
        query = supabase.table(table_name("bug_reports")).select("*")
        filters = filters or {}
        for key, value in filters.items():
            if value is None:
                continue
            column = column_name("bug_reports", key)
            query = query.eq(column, value)
        response = (
            query.order(column_name("bug_reports", "created_at"), desc=True)
            .execute()
        )
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
    payload = to_supabase_payload("bug_reports", payload)

    try:
        response = (
            supabase.table(table_name("bug_reports"))
            .update(payload)
            .eq(column_name("bug_reports", "id"), report_id)
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
        response = supabase.table(table_name("aoi_reports")).select("*").execute()
        rows = getattr(response, "data", None) or []
        _apply_aoi_aliases(rows)
        return rows, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch AOI reports: {exc}"


def fetch_fi_reports():
    """Retrieve all FI reports from the database."""
    supabase = _get_client()
    try:
        response = supabase.table(table_name("fi_reports")).select("*").execute()
        rows = getattr(response, "data", None) or []
        _apply_fi_aliases(rows)
        return rows, None
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
        response = supabase.table(table_name("combined_reports")).select("*").execute()
        rows = getattr(response, "data", None) or []
        _apply_combined_aliases(rows)
        return rows, None
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
    table_name_value = table_name(table)
    report_date_column = column_name(table, "report_date")

    while True:
        query = supabase.table(table_name_value).select("*")
        if order_column:
            query = query.order(column_name(table, order_column))
        if start_date:
            query = query.gte(report_date_column, start_date)
        if end_date:
            query = query.lte(report_date_column, end_date)
        query = query.range(offset, offset + page_size - 1)

        response = query.execute()
        batch = response.data or []
        rows.extend(batch)

        if len(batch) < page_size:
            break
        offset += page_size

    return rows


def _normalize_part_result_row(row: dict) -> dict:
    """Return a copy of ``row`` with standardised part analytics fields."""

    def _normalized_key(key: str) -> str:
        return (
            str(key)
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

    def _get_value(*aliases: str, default=None):
        for alias in aliases:
            if alias in normalized:
                value = normalized[alias]
                if value not in (None, ""):
                    return value
        return default

    def _get_string(*aliases: str) -> str | None:
        value = _get_value(*aliases)
        if value in (None, ""):
            return None
        return str(value).strip() or None

    def _get_float(*aliases: str) -> float | None:
        value = _get_value(*aliases)
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_bool(*aliases: str) -> bool | None:
        value = _get_value(*aliases)
        if isinstance(value, bool):
            return value
        if value in (None, ""):
            return None
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "y", "t"}:
            return True
        if text in {"false", "0", "no", "n", "f"}:
            return False
        return None

    normalized: dict[str, object] = {}
    for key, value in (row or {}).items():
        key_norm = _normalized_key(key)
        if key_norm not in normalized:
            normalized[key_norm] = value

    result = dict(row or {})

    date_value = _get_value("inspection_date", "report_date", "date", "inspected_date")
    if isinstance(date_value, datetime):
        inspection_date = date_value.date().isoformat()
    elif isinstance(date_value, date):
        inspection_date = date_value.isoformat()
    else:
        inspection_date = None
        if date_value not in (None, ""):
            text = str(date_value).strip()
            if text:
                try:
                    inspection_date = datetime.fromisoformat(text).date().isoformat()
                except ValueError:
                    inspection_date = text

    result["inspection_date"] = inspection_date
    result["part_number"] = _get_string("part_number", "partno", "part_num", "pn")
    result["board_serial"] = _get_string(
        "board_serial",
        "board_id",
        "panel_serial",
        "panel_id",
        "board",
    )
    result["assembly"] = _get_string("assembly", "assembly_name", "model", "model_name")
    result["line"] = _get_string("line", "line_name")
    result["program"] = _get_string("program", "program_name", "recipe")
    result["component_type"] = _get_string("component_type", "component", "componentname")
    result["component_family"] = _get_string("component_family", "family", "componentgroup")
    result["defect_code"] = _get_string("defect_code", "code", "defectcode")
    result["defect_type"] = _get_string("defect_type", "type", "defectcategory")
    result["operator"] = _get_string("operator", "operator_name", "operatorid")
    result["operator_disposition"] = _get_string(
        "operator_disposition",
        "disposition",
        "operator_result",
        "review_result",
    )
    result["operator_confirmation"] = _get_string(
        "operator_confirmation",
        "confirmation",
        "operator_confirmation_status",
    )

    result["offset_x"] = _get_float("offset_x", "x_offset", "delta_x")
    result["offset_y"] = _get_float("offset_y", "y_offset", "delta_y")
    result["offset_theta"] = _get_float("offset_theta", "theta", "rotation")
    result["offset_z"] = _get_float("offset_z", "z_offset", "delta_z")
    height = _get_float("height", "measured_height", "z_height")
    if height is None:
        height = _get_float("offset_height")
    result["height"] = height

    density = _get_float("defect_density", "density")
    result["defect_density"] = density

    false_call_flag = _get_bool("false_call", "is_false_call", "falsecall")
    if false_call_flag is None:
        disposition = (result.get("operator_disposition") or "").lower()
        if disposition:
            if "false" in disposition and "call" in disposition:
                false_call_flag = True
            elif disposition in {"confirmed", "ng", "reject", "scrap", "true"}:
                false_call_flag = False
    result["false_call"] = bool(false_call_flag)

    disposition_text = (result.get("operator_disposition") or "").strip().lower()
    if not result["operator_disposition"] and disposition_text:
        result["operator_disposition"] = disposition_text

    return result


def fetch_part_results(
    *,
    start_date: date | datetime | str | None = None,
    end_date: date | datetime | str | None = None,
    page_size: int = 1000,
) -> tuple[list[dict] | None, str | None]:
    """Return normalized SMT part inspection results from Supabase."""

    if page_size <= 0:
        return None, "page_size must be greater than zero"

    supabase, error = _ensure_supabase_client()
    if error:
        return [], error

    start_value = _normalize_date_for_query(start_date)
    end_value = _normalize_date_for_query(end_date)

    try:
        rows: list[dict] = []
        offset = 0
        while True:
            query = supabase.table(table_name("part_result_table")).select("*")
            inspection_column = column_name("part_result_table", "inspection_date")
            query = query.order(inspection_column)
            if start_value:
                query = query.gte(inspection_column, start_value)
            if end_value:
                query = query.lte(inspection_column, end_value)
            query = query.range(offset, offset + page_size - 1)

            response = query.execute()
            batch = response.data or []
            normalized_batch = [
                _normalize_part_result_row(item)
                for item in batch
                if isinstance(item, dict)
            ]
            rows.extend(normalized_batch)

            if len(batch) < page_size:
                break
            offset += page_size

        return rows, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch part results: {exc}"


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
            order_column="report_date",
        )
        data = _apply_report_date_offset(rows)
        data = [_normalize_ppm_row(row) for row in data or []]
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
            order_column="report_date",
        )
        data = _apply_report_date_offset(rows)
        data = [_normalize_dpm_row(row) for row in data or []]
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
        id_column = column_name("defects", "id")
        name_column = column_name("defects", "name")
        response = (
            supabase.table(table_name("defects"))
            .select(f"{id_column},{name_column}")
            .execute()
        )
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch defects: {exc}"

    catalog: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in response.data or []:
        raw_id = row.get(id_column)
        raw_name = row.get(name_column)
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
        payload = to_supabase_payload("aoi_reports", data)
        response = supabase.table(table_name("aoi_reports")).insert(payload).execute()
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
        mapped_rows = [to_supabase_payload("aoi_reports", row) for row in rows]
        response = supabase.table(table_name("aoi_reports")).insert(mapped_rows).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert AOI reports: {exc}"


def insert_fi_report(data: dict):
    """Insert a new FI report."""
    supabase = _get_client()
    try:
        payload = to_supabase_payload("fi_reports", data)
        response = supabase.table(table_name("fi_reports")).insert(payload).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert FI report: {exc}"


def insert_moat(data: dict):
    """Insert MOAT data."""
    supabase = _get_client()
    try:
        payload = to_supabase_payload("moat", data)
        response = supabase.table(table_name("moat")).insert(payload).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert MOAT data: {exc}"


def insert_moat_bulk(rows: list[dict]):
    """Insert multiple MOAT records at once."""
    supabase = _get_client()
    try:
        mapped_rows = [to_supabase_payload("moat", row) for row in rows]
        response = supabase.table(table_name("moat")).insert(mapped_rows).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert MOAT data: {exc}"


def insert_moat_dpm(data: dict):
    """Insert a single MOAT DPM record."""

    supabase = _get_client()
    try:
        payload = to_supabase_payload("moat_dpm", data)
        response = supabase.table(table_name("moat_dpm")).insert(payload).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to insert MOAT DPM data: {exc}"


def insert_moat_dpm_bulk(rows: list[dict]):
    """Insert multiple MOAT DPM records."""

    supabase = _get_client()
    try:
        mapped_rows = [to_supabase_payload("moat_dpm", row) for row in rows]
        response = supabase.table(table_name("moat_dpm")).insert(mapped_rows).execute()
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
        ppm_columns = [
            column_name("ppm_saved_queries", key)
            for key in (
                "id",
                "name",
                "type",
                "description",
                "start_date",
                "end_date",
                "value_source",
                "x_column",
                "y_agg",
                "chart_type",
                "line_color",
                "params",
                "created_at",
            )
        ]
        response = (
            supabase.table(table_name("ppm_saved_queries"))
            .select(",".join(ppm_columns))
            .order(column_name("ppm_saved_queries", "created_at"), desc=True)
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch saved queries: {exc}"


def fetch_dpm_saved_queries():
    """Retrieve saved chart queries for DPM analysis."""

    supabase = _get_client()
    try:
        dpm_columns = [
            column_name("dpm_saved_queries", key)
            for key in (
                "id",
                "name",
                "type",
                "description",
                "start_date",
                "end_date",
                "value_source",
                "x_column",
                "y_agg",
                "chart_type",
                "line_color",
                "params",
                "created_at",
            )
        ]
        response = (
            supabase.table(table_name("dpm_saved_queries"))
            .select(",".join(dpm_columns))
            .order(column_name("dpm_saved_queries", "created_at"), desc=True)
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
        payload = to_supabase_payload("ppm_saved_queries", data)
        response = supabase.table(table_name("ppm_saved_queries")).insert(payload).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to save chart query: {exc}"


def insert_dpm_saved_query(data: dict):
    """Insert a saved DPM chart query definition into Supabase."""

    supabase = _get_client()
    try:
        payload = to_supabase_payload("dpm_saved_queries", data)
        response = supabase.table(table_name("dpm_saved_queries")).insert(payload).execute()
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
        payload = to_supabase_payload(
            "ppm_saved_queries", {**data, "name": name}
        )
        response = (
            supabase.table(table_name("ppm_saved_queries"))
            .upsert(
                payload,
                on_conflict=column_name("ppm_saved_queries", "name"),
            )
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to update saved query: {exc}"


def update_dpm_saved_query(name: str, data: dict):
    """Update or upsert a saved DPM chart query definition by ``name``."""

    supabase = _get_client()
    try:
        payload = to_supabase_payload(
            "dpm_saved_queries", {**data, "name": name}
        )
        response = (
            supabase.table(table_name("dpm_saved_queries"))
            .upsert(
                payload,
                on_conflict=column_name("dpm_saved_queries", "name"),
            )
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
        aoi_columns = [
            column_name("aoi_saved_queries", key)
            for key in (
                "id",
                "name",
                "description",
                "start_date",
                "end_date",
                "params",
                "created_at",
            )
        ]
        response = (
            supabase.table(table_name("aoi_saved_queries"))
            .select(",".join(aoi_columns))
            .order(column_name("aoi_saved_queries", "created_at"), desc=True)
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch AOI saved queries: {exc}"


def insert_saved_aoi_query(data: dict):
    """Insert a saved AOI chart query definition into Supabase."""
    supabase = _get_client()
    try:
        payload = to_supabase_payload("aoi_saved_queries", data)
        response = supabase.table(table_name("aoi_saved_queries")).insert(payload).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to save AOI chart query: {exc}"


def update_saved_aoi_query(name: str, data: dict):
    """Update or upsert a saved AOI chart query by ``name``."""
    supabase = _get_client()
    try:
        payload = to_supabase_payload(
            "aoi_saved_queries", {**data, "name": name}
        )
        response = (
            supabase.table(table_name("aoi_saved_queries"))
            .upsert(
                payload,
                on_conflict=column_name("aoi_saved_queries", "name"),
            )
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to update AOI saved query: {exc}"


def fetch_saved_fi_queries():
    """Retrieve saved chart queries for the FI Daily Reports page."""
    supabase = _get_client()
    try:
        fi_columns = [
            column_name("fi_saved_queries", key)
            for key in (
                "id",
                "name",
                "description",
                "start_date",
                "end_date",
                "params",
                "created_at",
            )
        ]
        response = (
            supabase.table(table_name("fi_saved_queries"))
            .select(",".join(fi_columns))
            .order(column_name("fi_saved_queries", "created_at"), desc=True)
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to fetch FI saved queries: {exc}"


def insert_saved_fi_query(data: dict):
    """Insert a saved FI chart query definition into Supabase."""
    supabase = _get_client()
    try:
        payload = to_supabase_payload("fi_saved_queries", data)
        response = supabase.table(table_name("fi_saved_queries")).insert(payload).execute()
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to save FI chart query: {exc}"


def update_saved_fi_query(name: str, data: dict):
    """Update or upsert a saved FI chart query by ``name``."""
    supabase = _get_client()
    try:
        payload = to_supabase_payload(
            "fi_saved_queries", {**data, "name": name}
        )
        response = (
            supabase.table(table_name("fi_saved_queries"))
            .upsert(
                payload,
                on_conflict=column_name("fi_saved_queries", "name"),
            )
            .execute()
        )
        return response.data, None
    except Exception as exc:  # pragma: no cover - network errors
        return None, f"Failed to update FI saved query: {exc}"
