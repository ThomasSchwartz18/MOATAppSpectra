import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd

from aoi_grading import compute_aoi_grades
from fi_utils import parse_fi_rejections


def test_aoi_grades_excludes_non_aoi_defects():
    row = {
        'aoi_Job Number': 'J1',
        'aoi_Operator': 'Op',
        'aoi_Date': '2024-01-01',
        'aoi_Quantity Inspected': 10,
        'aoi_Quantity Rejected': 0,
        'fi_Date': '2024-01-02',
        'fi_Quantity Inspected': 10,
        'fi_Quantity Rejected': 60,
        'fi_Additional Information': 'U3 Solder Holes (1), U1 Missing Coating (59)',
    }
    phrases_path = Path('config/non_aoi_phrases.json')
    ignore_phrases = json.loads(phrases_path.read_text())
    row['fi_Quantity Rejected'] = parse_fi_rejections(
        row['fi_Additional Information'], ignore_phrases
    )
    df = pd.DataFrame([row])
    grades, breakdown = compute_aoi_grades(df)
    assert breakdown['fi_rejects_job'].iloc[0] == 1
