import os
import sys
import math
from pathlib import Path

import numpy as np
import pytest
from flask import Flask, session

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('USER_PASSWORD', 'test')
os.environ.setdefault('ADMIN_PASSWORD', 'test')

from app.main import routes


@pytest.fixture
def app(monkeypatch):
    app = Flask(__name__)
    app.secret_key = 'test'
    app.config['NON_AOI_PHRASES'] = ['Missing Coating']
    row = {
        'aoi_Date': '2024-01-01',
        'aoi_Shift': '1',
        'aoi_Operator': 'Op1',
        'aoi_Job Number': 'J1',
        'aoi_Assembly': 'M1',
        'aoi_Rev': 'R1',
        'fi_Date': '2024-01-05',
        'fi_Additional Information': 'Missing Coating (5), Solder Bridge (1)',
        'aoi_Quantity Inspected': 10,
        'aoi_Quantity Rejected': 0,
        'fi_Quantity Rejected': 6,
        'fi_Quantity Inspected': 10,
    }
    monkeypatch.setattr(routes, 'fetch_combined_reports', lambda: ([row], None))
    return app


def test_shift_effect_excludes_non_aoi(app):
    with app.test_request_context():
        session['username'] = 'user'
        data = routes.aoi_grades_shift_effect().get_json()
    assert data['shift_stats']['1']['median'] == pytest.approx(100.0)


def test_learning_curves_excludes_non_aoi(app):
    with app.test_request_context():
        session['username'] = 'user'
        data = routes.aoi_grades_learning_curves().get_json()
    assert data['Op1']['rates'][0] == pytest.approx(100.0)


def test_gap_risk_excludes_non_aoi(app):
    with app.test_request_context():
        session['username'] = 'user'
        data = routes.aoi_grades_gap_risk().get_json()
    idx = data['labels'].index('4–7d')
    assert data['fi_share'][idx] == pytest.approx(1.0)


def test_program_trend_excludes_non_aoi(app):
    with app.test_request_context():
        session['username'] = 'user'
        data = routes.aoi_grades_program_trend().get_json()
    assert data['datasets'][0]['data'][0] == pytest.approx(100.0)


def test_adjusted_operator_ranking_excludes_non_aoi(app):
    with app.test_request_context():
        session['username'] = 'user'
        data = routes.aoi_grades_adjusted_operator_ranking().get_json()
    effect = data['effects'][0]['effect']
    X = np.array([[1.0, math.log(10), 1.0]])
    lam = 1.0
    XtX = X.T @ X
    A = XtX + lam * np.eye(X.shape[1])
    b = X.T @ np.array([100.0])
    expected = np.linalg.solve(A, b)[2]
    assert effect == pytest.approx(expected)
