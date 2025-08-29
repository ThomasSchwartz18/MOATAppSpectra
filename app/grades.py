from collections import defaultdict
from typing import Iterable


def compute_operator_grades(rows: Iterable[dict]) -> dict:
    """Compute final grade per operator from combined report rows.

    The algorithm assigns a portion of final inspection (FI) rejects to each
    operator based on their share of AOI quantity inspected for a given job.

    Args:
        rows: Iterable of dictionaries from the ``combined_reports`` table. Each
            row should contain at minimum the keys ``Job Number`` (or
            ``aoi_Job Number``), ``Operator`` (or ``aoi_Operator``),
            ``aoi_Quantity Inspected`` and ``fi_Quantity Rejected``.

    Returns:
        Dict mapping operator name to a dictionary with keys:
            ``inspected`` -- total AOI quantity inspected by the operator,
            ``weighted_missed`` -- weighted missed defects attributed to the
            operator, and ``grade`` -- the operator's final grade expressed as a
            fraction between 0 and 1.
    """
    # Sum AOI quantities per job to compute operator share
    job_totals: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        job = row.get("aoi_Job Number") or row.get("Job Number")
        inspected = float(row.get("aoi_Quantity Inspected", 0) or 0)
        if job is not None:
            job_totals[job] += inspected

    # Accumulate statistics per operator
    operator_stats: defaultdict[str, dict] = defaultdict(lambda: {"inspected": 0.0, "weighted_missed": 0.0})
    for row in rows:
        job = row.get("aoi_Job Number") or row.get("Job Number")
        operator = row.get("aoi_Operator") or row.get("Operator")
        inspected = float(row.get("aoi_Quantity Inspected", 0) or 0)
        fi_rejected = float(
            row.get("fi_Quantity Rejected")
            or row.get("Quantity Rejected")
            or 0
        )
        total_for_job = job_totals.get(job, 0)
        share = inspected / total_for_job if total_for_job else 0
        weighted_missed = fi_rejected * share

        stats = operator_stats[operator]
        stats["inspected"] += inspected
        stats["weighted_missed"] += weighted_missed

    # Compute final grade per operator
    results = {}
    for operator, stats in operator_stats.items():
        inspected = stats["inspected"]
        missed = stats["weighted_missed"]
        grade = 1 - (missed / inspected) if inspected else 0.0
        results[operator] = {
            "inspected": inspected,
            "weighted_missed": missed,
            "grade": grade,
        }
    return results


def calculate_aoi_grades(rows: Iterable[dict]) -> dict:
    """Wrapper around :func:`compute_operator_grades` for clarity.

    Args:
        rows: Iterable of dictionaries from the ``combined_reports`` table.

    Returns:
        The result of :func:`compute_operator_grades`.
    """

    return compute_operator_grades(rows)
