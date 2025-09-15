from app.db import _apply_report_date_offset


def test_apply_report_date_offset():
    rows = [
        {"Report Date": "2024-08-02"},
        {"report_date": "2024-08-03"},
        {"Report Date": None},
    ]
    adjusted = _apply_report_date_offset(rows)
    assert adjusted[0]["Report Date"] == "2024-08-01"
    assert adjusted[1]["report_date"] == "2024-08-02"
    # None values should be left untouched
    assert adjusted[2]["Report Date"] is None
