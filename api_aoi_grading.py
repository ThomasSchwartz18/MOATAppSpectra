from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, Body

from aoi_grading import compute_aoi_grades


app = FastAPI(title="AOI Operator Reliability Grading API")


@app.post("/grades")
def grades_endpoint(
    payload: Dict[str, Any] = Body(..., example={
        "combined_reports": [
            {
                "aoi_Job Number": "J1",
                "aoi_Operator": "Alice",
                "aoi_Date": "2024-07-01",
                "aoi_Quantity Inspected": 100,
                "aoi_Quantity Rejected": 2,
                "fi_Date": "2024-07-03",
                "fi_Quantity Inspected": 100,
                "fi_Quantity Rejected": 6,
            }
        ],
        "k_severity": 40.0,
    })
):
    rows: List[Dict[str, Any]] = payload.get("combined_reports", [])
    k_severity: Optional[float] = payload.get("k_severity")

    df = pd.DataFrame(rows)
    grades_df, breakdown_df = compute_aoi_grades(df, k_severity=float(k_severity) if k_severity is not None else 40.0)
    return {
        "grades": grades_df.to_dict(orient="records"),
        "count": len(grades_df),
    }


@app.post("/breakdown")
def breakdown_endpoint(payload: Dict[str, Any]):
    rows: List[Dict[str, Any]] = payload.get("combined_reports", [])
    df = pd.DataFrame(rows)
    grades_df, breakdown_df = compute_aoi_grades(df, k_severity=float(payload.get("k_severity", 40.0)))
    return {
        "breakdown": breakdown_df.to_dict(orient="records"),
        "grades_summary": grades_df.to_dict(orient="records"),
        "count": len(breakdown_df),
    }


# To run locally:
#   uvicorn api_aoi_grading:app --reload --port 8080

