from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
    abort,
    request,
    jsonify,
)
from functools import wraps

from app.db import (
    fetch_aoi_reports,
    fetch_fi_reports,
    fetch_moat,
    fetch_recent_moat,
    fetch_saved_queries,
    insert_saved_query,
    update_saved_query,
    insert_aoi_report,
    insert_fi_report,
    insert_moat,
)

main_bp = Blueprint('main', __name__)


@main_bp.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('home.html', username=session.get('username'))


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get('username') != 'ADMIN':
            abort(403)
        return view(**kwargs)
    return wrapped_view


@main_bp.route('/admin')
@admin_required
def admin_panel():
    return render_template('admin.html', username=session.get('username'))


@main_bp.route('/aoi_reports', methods=['GET'])
def get_aoi_reports():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    data, error = fetch_aoi_reports()
    if error:
        abort(500, description=error)
    return jsonify(data)


@main_bp.route('/aoi_reports', methods=['POST'])
@admin_required
def add_aoi_report():
    payload = request.get_json() or {}
    data, error = insert_aoi_report(payload)
    if error:
        abort(500, description=error)
    return jsonify(data), 201


@main_bp.route('/fi_reports', methods=['GET'])
def get_fi_reports():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    data, error = fetch_fi_reports()
    if error:
        abort(500, description=error)
    return jsonify(data)


@main_bp.route('/fi_reports', methods=['POST'])
@admin_required
def add_fi_report():
    payload = request.get_json() or {}
    data, error = insert_fi_report(payload)
    if error:
        abort(500, description=error)
    return jsonify(data), 201


@main_bp.route('/moat', methods=['GET'])
def get_moat_data():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    data, error = fetch_moat()
    if error:
        abort(500, description=error)
    return jsonify(data)


@main_bp.route('/moat', methods=['POST'])
@admin_required
def add_moat_data():
    payload = request.get_json() or {}
    data, error = insert_moat(payload)
    if error:
        abort(500, description=error)
    return jsonify(data), 201


@main_bp.route('/moat_preview', methods=['GET'])
def moat_preview():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    data, error = fetch_recent_moat()
    if error:
        abort(500, description=error)
    if not data:
        return jsonify({
            "models": [],
            "avg_false_calls": [],
            "overall_avg": 0,
            "start_date": None,
            "end_date": None,
        })
    from collections import defaultdict

    grouped = defaultdict(lambda: {"falsecall": 0, "boards": 0})
    dates = []
    for row in data:
        fc = row.get('FalseCall Parts') or row.get('falsecall_parts') or 0
        boards = row.get('Total Boards') or row.get('total_boards') or 0
        model = row.get('Model Name') or row.get('model_name') or 'Unknown'
        date = row.get('Report Date') or row.get('report_date')
        if date:
            dates.append(str(date))
        grouped[model]["falsecall"] += fc
        grouped[model]["boards"] += boards

    models, averages = [], []
    total_avg = 0
    for model, vals in grouped.items():
        avg = (vals["falsecall"] / vals["boards"]) if vals["boards"] else 0
        models.append(model)
        averages.append(avg)
        total_avg += avg

    overall_avg = total_avg / len(averages) if averages else 0
    start_date = min(dates) if dates else None
    end_date = max(dates) if dates else None
    return jsonify({
        "models": models,
        "avg_false_calls": averages,
        "overall_avg": overall_avg,
        "start_date": start_date,
        "end_date": end_date,
    })


@main_bp.route('/analysis/ppm', methods=['GET'])
def ppm_analysis():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('ppm_analysis.html', username=session.get('username'))


@main_bp.route('/analysis/ppm/data', methods=['GET'])
def ppm_data():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    chart_type = request.args.get('type', 'avg_false_calls_per_assembly')
    start = request.args.get('start_date')
    end = request.args.get('end_date')

    # Currently only supports avg_false_calls_per_assembly; ordered by date
    data, error = fetch_moat()
    if error:
        abort(500, description=error)
    if not data:
        return jsonify({"labels": [], "values": []})

    from collections import defaultdict
    from datetime import datetime

    def parse_date(d):
        if not d:
            return None
        # Accept date or datetime strings
        try:
            return datetime.fromisoformat(str(d)).date()
        except Exception:
            return None

    grouped = defaultdict(lambda: {"falsecall": 0, "boards": 0})
    for row in data:
        date = row.get('Report Date') or row.get('report_date')
        dt = parse_date(date)
        if not dt:
            continue
        if start:
            sdt = parse_date(start)
            if sdt and dt < sdt:
                continue
        if end:
            edt = parse_date(end)
            if edt and dt > edt:
                continue
        fc = row.get('FalseCall Parts') or row.get('falsecall_parts') or 0
        boards = row.get('Total Boards') or row.get('total_boards') or 0
        grouped[dt]["falsecall"] += fc
        grouped[dt]["boards"] += boards

    ordered_dates = sorted(list(grouped.keys()))
    labels = [d.isoformat() for d in ordered_dates]
    values = []
    for d in ordered_dates:
        g = grouped[d]
        values.append((g["falsecall"] / g["boards"]) if g["boards"] else 0)

    return jsonify({"labels": labels, "values": values, "type": chart_type})


@main_bp.route('/analysis/ppm/saved', methods=['GET', 'POST', 'PUT'])
def ppm_saved_queries():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    if request.method == 'GET':
        data, error = fetch_saved_queries()
        if error:
            abort(500, description=error)
        return jsonify(data)

    payload = request.get_json() or {}
    keys = [
        "name",
        "type",
        "params",
        "description",
        "start_date",
        "end_date",
        "value_source",
        "x_column",
        "y_agg",
        "chart_type",
        "line_color",
    ]
    payload = {k: payload.get(k) for k in keys if k in payload}
    overwrite = request.method == 'PUT' or request.args.get('overwrite')
    if overwrite:
        name = payload.get('name')
        data, error = update_saved_query(name, payload)
        status = 200
    else:
        data, error = insert_saved_query(payload)
        status = 201
    if error:
        abort(500, description=error)
    return jsonify(data), status
