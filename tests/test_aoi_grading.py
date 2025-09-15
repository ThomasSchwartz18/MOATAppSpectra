import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd

from aoi_grading import compute_aoi_grades, default_alpha_from_gap


def test_default_alpha_from_gap_rules():
    assert math.isclose(default_alpha_from_gap(float('nan')), 0.70, rel_tol=1e-9)
    assert default_alpha_from_gap(0) == 0.85
    assert default_alpha_from_gap(1) == 0.85
    assert default_alpha_from_gap(2) == 0.70
    assert default_alpha_from_gap(5) == 0.60
    assert default_alpha_from_gap(10) == 0.50


def test_basic_breakdown_and_grades():
    # One job with two operators; ensure attribution splits by scope-adjusted share.
    rows = [
        {
            'aoi_Job Number': 'J1',
            'aoi_Operator': 'Alice',
            'aoi_Date': '2024-07-01',
            'aoi_Program': 'Alpha',
            'aoi_Quantity Inspected': 100,
            'aoi_Quantity Rejected': 5,
            'fi_Date': '2024-07-03',
            'fi_Quantity Inspected': 150,
            'fi_Quantity Rejected': 2,  # Job-level R_j = 2
        },
        {
            'aoi_Job Number': 'J1',
            'aoi_Operator': 'Bob',
            'aoi_Date': '2024-07-02',
            'aoi_Program': 'Alpha',
            'aoi_Quantity Inspected': 50,
            'aoi_Quantity Rejected': 0,
            'fi_Date': '2024-07-03',
            'fi_Quantity Inspected': 150,
            'fi_Quantity Rejected': 2,
        },
    ]
    df = pd.DataFrame(rows)
    grades, breakdown = compute_aoi_grades(df)

    # Breakdown has same number of rows as input, and expected columns
    assert len(breakdown) == 2
    for col in [
        'job', 'aoi_operator', 'aoi_date', 'aoi_passed', 'scope_beta', 'share_passed',
        'fi_rejects_job', 'fi_inspected_job', 'gap_days_median', 'alpha_job', 'attributed_misses',
    ]:
        assert col in breakdown.columns

    # Shares by scope-adjusted passed: Alice passed 95, Bob 50 → total 145
    alice_share = breakdown.loc[breakdown['aoi_operator'] == 'Alice', 'share_passed'].iloc[0]
    bob_share = breakdown.loc[breakdown['aoi_operator'] == 'Bob', 'share_passed'].iloc[0]
    assert math.isclose(alice_share + bob_share, 1.0, rel_tol=1e-9)
    assert alice_share > bob_share

    # Grades dataframe has two operators and expected fields
    assert set(grades['aoi_operator']) == {'Alice', 'Bob'}
    for col in ['jobs', 'total_aoi_passed', 'total_attr_misses', 'misses_per_1k_passes', 'grade']:
        assert col in grades.columns

    # Grade bounds [0, 100]
    assert grades['grade'].between(0, 100).all()


def test_zero_scope_no_penalty():
    # All AOI passed are zero → share is zero, no attribution, grade 100
    rows = [
        {
            'aoi_Job Number': 'J2',
            'aoi_Operator': 'Cara',
            'aoi_Date': '2024-07-10',
            'aoi_Program': 'Alpha',
            'aoi_Quantity Inspected': 10,
            'aoi_Quantity Rejected': 10,
            'fi_Date': '2024-07-12',
            'fi_Quantity Inspected': 10,
            'fi_Quantity Rejected': 5,
        },
        {
            'aoi_Job Number': 'J2',
            'aoi_Operator': 'Dan',
            'aoi_Date': '2024-07-10',
            'aoi_Program': 'Alpha',
            'aoi_Quantity Inspected': 5,
            'aoi_Quantity Rejected': 5,
            'fi_Date': '2024-07-12',
            'fi_Quantity Inspected': 10,
            'fi_Quantity Rejected': 5,
        },
    ]
    df = pd.DataFrame(rows)
    grades, breakdown = compute_aoi_grades(df)
    # No one gets penalized; attributed_misses all zeros
    assert (breakdown['attributed_misses'] == 0).all()
    # total_aoi_passed == 0 for each operator ⇒ grade 100
    assert (grades['total_aoi_passed'] == 0).all()
    assert (grades['grade'] == 100).all()


def test_beta_scope_custom_function():
    # Bob out of scope via beta=0 ⇒ Alice gets all job share
    rows = [
        {
            'aoi_Job Number': 'J3',
            'aoi_Operator': 'Alice',
            'aoi_Date': '2024-07-01',
            'aoi_Program': 'Alpha',
            'aoi_Quantity Inspected': 60,
            'aoi_Quantity Rejected': 0,
            'fi_Date': '2024-07-02',
            'fi_Quantity Inspected': 60,
            'fi_Quantity Rejected': 4,
        },
        {
            'aoi_Job Number': 'J3',
            'aoi_Operator': 'Bob',
            'aoi_Date': '2024-07-01',
            'aoi_Program': 'Alpha',
            'aoi_Quantity Inspected': 40,
            'aoi_Quantity Rejected': 0,
            'fi_Date': '2024-07-02',
            'fi_Quantity Inspected': 60,
            'fi_Quantity Rejected': 4,
        },
    ]
    df = pd.DataFrame(rows)

    def beta(op: str, _row: pd.Series) -> float:
        return 0.0 if op == 'Bob' else 1.0

    grades, breakdown = compute_aoi_grades(df, beta_scope_fn=beta)
    alice_share = breakdown.loc[breakdown['aoi_operator'] == 'Alice', 'share_passed'].iloc[0]
    bob_share = breakdown.loc[breakdown['aoi_operator'] == 'Bob', 'share_passed'].iloc[0]
    assert math.isclose(alice_share, 1.0, rel_tol=1e-9)
    assert math.isclose(bob_share, 0.0, rel_tol=1e-9)


def test_missing_dates_use_default_alpha():
    rows = [
        {
            'aoi_Job Number': 'J4',
            'aoi_Operator': 'Alice',
            'aoi_Program': 'Alpha',
            'aoi_Quantity Inspected': 10,
            'aoi_Quantity Rejected': 0,
            # No dates provided
            'fi_Quantity Inspected': 10,
            'fi_Quantity Rejected': 3,
        }
    ]
    df = pd.DataFrame(rows)
    grades, breakdown = compute_aoi_grades(df)
    alpha = breakdown['alpha_job'].iloc[0]
    assert math.isclose(alpha, 0.70, rel_tol=1e-9)

