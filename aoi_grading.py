from __future__ import annotations

from typing import Callable, Tuple

import pandas as pd


def default_alpha_from_gap(days: float) -> float:
    """Map AOI→FI median gap (days) to a downstream discount factor.

    Rules:
    - NaN → 0.70
    - <= 1 → 0.85
    - <= 3 → 0.70
    - <= 7 → 0.60
    - else → 0.50
    """
    if pd.isna(days):
        return 0.70
    if days <= 1:
        return 0.85
    if days <= 3:
        return 0.70
    if days <= 7:
        return 0.60
    return 0.50


def default_beta_scope(_operator: str, _row: pd.Series) -> float:
    """Scope weighting for an AOI row.

    1.0 = fully in scope; 0.0 = out-of-scope (e.g., SMT vs TH mismatch).
    Default behavior: everything in scope (1.0).
    """
    return 1.0


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def compute_aoi_grades(
    combined_reports: pd.DataFrame,
    *,
    k_severity: float = 40.0,
    alpha_fn: Callable[[float], float] | None = None,
    beta_scope_fn: Callable[[str, pd.Series], float] | None = None,
    col_job: str = "aoi_Job Number",
    col_op: str = "aoi_Operator",
    col_aoi_date: str = "aoi_Date",
    col_aoi_inspected: str = "aoi_Quantity Inspected",
    col_aoi_rejected: str = "aoi_Quantity Rejected",
    col_fi_date: str = "fi_Date",
    col_fi_inspected: str = "fi_Quantity Inspected",
    col_fi_rejected: str = "fi_Quantity Rejected",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute per-operator grades and job/operator attribution breakdown.

    Returns (grades_df, breakdown_df).

    grades_df columns:
    - aoi_operator
    - jobs
    - total_aoi_passed
    - total_attr_misses
    - misses_per_1k_passes
    - grade (0–100), sorted DESC by grade

    breakdown_df columns (one row per original AOI row, i.e., operator-per-job record):
    - job
    - aoi_operator
    - aoi_date
    - aoi_passed
    - scope_beta
    - share_passed
    - fi_rejects_job
    - fi_inspected_job
    - gap_days_median
    - alpha_job
    - attributed_misses
    """

    if combined_reports is None or len(combined_reports) == 0:
        empty_grades = pd.DataFrame(
            columns=[
                "aoi_operator",
                "jobs",
                "total_aoi_passed",
                "total_attr_misses",
                "misses_per_1k_passes",
                "grade",
            ]
        )
        empty_breakdown = pd.DataFrame(
            columns=[
                "job",
                "aoi_operator",
                "aoi_date",
                "aoi_passed",
                "scope_beta",
                "share_passed",
                "fi_rejects_job",
                "fi_inspected_job",
                "gap_days_median",
                "alpha_job",
                "attributed_misses",
            ]
        )
        return empty_grades, empty_breakdown

    df = combined_reports.copy()

    # Normalize and coerce numeric columns.
    for col in [col_aoi_inspected, col_aoi_rejected, col_fi_inspected, col_fi_rejected]:
        if col in df.columns:
            df[col] = _to_num(df[col])
        else:
            df[col] = 0.0

    # Parse dates.
    df[col_aoi_date] = pd.to_datetime(df.get(col_aoi_date, pd.NaT), errors="coerce")
    df[col_fi_date] = pd.to_datetime(df.get(col_fi_date, pd.NaT), errors="coerce")

    # Compute AOI-passed boards per row, clipped at 0.
    df["aoi_passed"] = (df[col_aoi_inspected] - df[col_aoi_rejected]).clip(lower=0.0)

    # Ensure required identifiers exist.
    if col_job not in df.columns:
        df[col_job] = None
    if col_op not in df.columns:
        df[col_op] = None

    # Job-level aggregates for FI totals.
    job_group = df.groupby(col_job, dropna=False)
    df["fi_rejects_job"] = job_group[col_fi_rejected].transform("max").fillna(0.0)
    df["fi_inspected_job"] = job_group[col_fi_inspected].transform("max").fillna(0.0)

    # Gap days per row then median per job.
    gap_days = (df[col_fi_date] - df[col_aoi_date]).dt.days
    # Compute median per job (ignoring NaNs automatically).
    gap_median_by_job = gap_days.groupby(df[col_job]).transform("median")
    df["gap_days_median"] = gap_median_by_job

    # alpha per job via provided function or default.
    alpha_func = alpha_fn or default_alpha_from_gap
    # Vectorize by mapping unique medians then joining back.
    unique_jobs = df[[col_job, "gap_days_median"]].drop_duplicates()
    unique_jobs["alpha_job"] = unique_jobs["gap_days_median"].map(alpha_func)
    df = df.merge(unique_jobs[[col_job, "alpha_job"]], on=col_job, how="left")

    # Beta scope weighting per row (can be fully vectorized if default).
    if beta_scope_fn is None or beta_scope_fn is default_beta_scope:
        df["scope_beta"] = 1.0
    else:
        # Apply row-wise with minimal overhead.
        def _row_beta(row: pd.Series) -> float:
            try:
                return float(beta_scope_fn(row.get(col_op), row))
            except Exception:
                return 1.0

        df["scope_beta"] = df.apply(_row_beta, axis=1)

    # Scope-adjusted passed.
    df["scope_passed"] = df["aoi_passed"] * df["scope_beta"]

    # Recompute job grouping to include new columns.
    job_group = df.groupby(col_job, dropna=False)

    # Per-job total scope; compute share within job.
    total_scope = job_group["scope_passed"].transform("sum")
    # Avoid division by zero: where total_scope == 0, share = 0
    df["share_passed"] = 0.0
    nonzero = total_scope > 0
    df.loc[nonzero, "share_passed"] = df.loc[nonzero, "scope_passed"] / total_scope[nonzero]

    # Attributed misses per row for the job.
    df["attributed_misses"] = df["alpha_job"].fillna(default_alpha_from_gap(float("nan"))) * df[
        "share_passed"
    ] * df["fi_rejects_job"].fillna(0.0)

    # Build breakdown output with required columns and names.
    breakdown_cols = {
        col_job: "job",
        col_op: "aoi_operator",
        col_aoi_date: "aoi_date",
    }
    breakdown_df = df.assign(**{v: df[k] for k, v in breakdown_cols.items()})[[
        "job",
        "aoi_operator",
        "aoi_date",
        "aoi_passed",
        "scope_beta",
        "share_passed",
        "fi_rejects_job",
        "fi_inspected_job",
        "gap_days_median",
        "alpha_job",
        "attributed_misses",
    ]].copy()

    # Aggregate by operator for grades.
    op_group = df.groupby(col_op, dropna=False)
    agg = op_group.agg(
        total_aoi_passed=("aoi_passed", "sum"),
        total_attr_misses=("attributed_misses", "sum"),
        jobs=(col_job, pd.Series.nunique),
    ).reset_index()
    agg.rename(columns={col_op: "aoi_operator"}, inplace=True)

    # misses_per_1k_passes and grade.
    denom = agg["total_aoi_passed"].replace(0, pd.NA)
    misses_per_1k = (1000.0 * agg["total_attr_misses"] / denom).fillna(0.0)
    agg["misses_per_1k_passes"] = misses_per_1k
    agg["grade"] = (100.0 - k_severity * misses_per_1k).clip(lower=0.0, upper=100.0)

    grades_df = agg.sort_values(by="grade", ascending=False).reset_index(drop=True)

    return grades_df, breakdown_df

