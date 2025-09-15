from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
    abort,
    request,
    jsonify,
    current_app,
    send_file,
)
from functools import wraps
import csv
import io
import os
import re
from datetime import datetime, date
from zoneinfo import ZoneInfo
from openpyxl import load_workbook
import xlrd
import base64
import math
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    matplotlib = None
    plt = None

from app.db import (
    fetch_aoi_reports,
    fetch_combined_reports,
    fetch_fi_reports,
    fetch_moat,
    fetch_recent_moat,
    fetch_saved_queries,
    fetch_saved_aoi_queries,
    fetch_saved_fi_queries,
    insert_saved_query,
    update_saved_query,
    insert_saved_aoi_query,
    update_saved_aoi_query,
    insert_saved_fi_query,
    update_saved_fi_query,
    insert_aoi_report,
    insert_aoi_reports_bulk,
    insert_fi_report,
    insert_moat,
    insert_moat_bulk,
)

from app.grades import calculate_aoi_grades
from fi_utils import parse_fi_rejections

# Helpers for AOI Grades analytics
from collections import defaultdict, Counter

def _parse_date(val):
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val)).date()
    except Exception:
        return None


def _aoi_passed(row):
    ins = float(row.get('aoi_Quantity Inspected') or row.get('Quantity Inspected') or 0)
    rej = float(row.get('aoi_Quantity Rejected') or row.get('Quantity Rejected') or 0)
    v = ins - rej
    return v if v > 0 else 0


def _fi_rejected(row):
    return float(row.get('fi_Quantity Rejected') or 0)


def _fi_inspected(row):
    return float(row.get('fi_Quantity Inspected') or 0)


def _gap_days(row):
    a = _parse_date(row.get('aoi_Date'))
    f = _parse_date(row.get('fi_Date'))
    if a and f:
        return (f - a).days
    return None


def _predict_counts(inspected: float, rejected: float, boards: float) -> dict[str, float]:
    """Compute predicted reject count and yield based on historical rates."""
    reject_rate = (rejected / inspected) if inspected else 0.0
    predicted_rejects = reject_rate * boards
    predicted_yield = (
        (boards - predicted_rejects) / boards * 100.0 if boards else 0.0
    )
    return {"predictedRejects": predicted_rejects, "predictedYield": predicted_yield}


def _aggregate_forecast(
    assemblies: list[str], moat_rows: list[dict], aoi_rows: list[dict]
) -> list[dict]:
    """Aggregate MOAT and AOI data for selected assemblies."""
    by_name = {a.lower(): a for a in assemblies if a}
    results: list[dict] = []
    for key, original in by_name.items():
        boards = 0.0
        false_calls = 0.0
        for row in moat_rows or []:
            asm = (
                row.get("Assembly")
                or row.get("Model")
                or row.get("Model Name")
                or ""
            )
            if asm and asm.strip().lower() == key:
                try:
                    boards += float(
                        row.get("Total Boards") or row.get("total_boards") or 0
                    )
                    false_calls += float(
                        row.get("FalseCall Parts")
                        or row.get("falsecall_parts")
                        or 0
                    )
                except (TypeError, ValueError):
                    continue
        inspected = 0.0
        rejected = 0.0
        for row in aoi_rows or []:
            asm = row.get("Assembly") or row.get("aoi_Assembly") or ""
            if asm and asm.strip().lower() == key:
                try:
                    inspected += float(
                        row.get("Quantity Inspected")
                        or row.get("aoi_Quantity Inspected")
                        or 0
                    )
                    rejected += float(
                        row.get("Quantity Rejected")
                        or row.get("aoi_Quantity Rejected")
                        or 0
                    )
                except (TypeError, ValueError):
                    continue
        avg_fc = false_calls / boards if boards else 0.0
        predicted_fc = avg_fc * boards
        preds = _predict_counts(inspected, rejected, boards)
        yield_pct = (
            (inspected - rejected) / inspected * 100.0 if inspected else 0.0
        )
        results.append(
            {
                "assembly": original,
                "boards": boards,
                "falseCalls": false_calls,
                "avgFalseCalls": avg_fc,
                "predictedFalseCalls": predicted_fc,
                "inspected": inspected,
                "rejected": rejected,
                "yield": yield_pct,
                **preds,
            }
        )
    return results


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


@main_bp.route('/aoi_reports/upload', methods=['POST'])
@admin_required
def upload_aoi_reports():
    """Upload a CSV file of AOI reports."""
    uploaded = request.files.get('file')
    if not uploaded or uploaded.filename == '':
        abort(400, description='No file provided')

    stream = io.StringIO(uploaded.stream.read().decode('utf-8'))
    reader = csv.DictReader(stream)
    required_columns = [
        'Date',
        'Shift',
        'Operator',
        'Customer',
        'Program',
        'Assembly',
        'Rev',
        'Job Number',
        'Quantity Inspected',
        'Quantity Rejected',
        'Additional Information',
    ]
    if reader.fieldnames != required_columns:
        abort(400, description='CSV must contain the required columns')

    rows = []
    for row in reader:
        # Copy required columns (including 'Program') for each record
        current = {col: row.get(col, '') for col in required_columns}
        date_str = current.get('Date')
        if date_str:
            try:
                dt = datetime.strptime(date_str, '%m/%d/%Y')
                current['Date'] = dt.date().isoformat()
            except ValueError:
                pass
        rows.append(current)
    if not rows:
        return jsonify({'inserted': 0}), 200

    data, error = insert_aoi_reports_bulk(rows)
    if error:
        abort(500, description=error)
    return jsonify({'inserted': len(rows)}), 201


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


@main_bp.route('/fi_reports/upload', methods=['POST'])
@admin_required
def upload_fi_reports():
    """Upload a CSV file of FI reports."""
    uploaded = request.files.get('file')
    if not uploaded or uploaded.filename == '':
        abort(400, description='No file provided')

    stream = io.StringIO(uploaded.stream.read().decode('utf-8'))
    reader = csv.DictReader(stream)
    required_columns = [
        'Date',
        'Shift',
        'Operator',
        'Customer',
        'Assembly',
        'Rev',
        'Job Number',
        'Quantity Inspected',
        'Quantity Rejected',
        'Additional Information',
    ]
    if reader.fieldnames != required_columns:
        abort(400, description='CSV must contain the required columns')

    rows = [{col: row.get(col, '') for col in required_columns} for row in reader]
    if not rows:
        return jsonify({'inserted': 0}), 200

    inserted = 0
    for r in rows:
        _, err = insert_fi_report(r)
        if err:
            abort(500, description=err)
        inserted += 1
    return jsonify({'inserted': inserted}), 201


@main_bp.route('/ppm_reports/upload', methods=['POST'])
@admin_required
def upload_ppm_reports():
    """Upload an XLS or XLSX PPM report and store rows in the MOAT table."""
    uploaded = request.files.get('file')
    if not uploaded or uploaded.filename == '':
        abort(400, description='No file provided')

    base = os.path.splitext(os.path.basename(uploaded.filename))[0]
    m = re.match(
        r"^PPMReportControl\s+(\d{4}-\d{2}-\d{2})(?:\s+to\s+(\d{4}-\d{2}-\d{2}))?\s+(L\w+)$",
        base,
        re.IGNORECASE,
    )
    if not m:
        abort(
            400,
            description=(
                'Filename must be "PPMReportControl YYYY-MM-DD LX" or '
                '"PPMReportControl YYYY-MM-DD to YYYY-MM-DD LX"'
            ),
        )
    start_date, end_date, line = m.groups()
    report_date = end_date or start_date

    try:
        uploaded.stream.seek(0)
        if uploaded.filename.lower().endswith('.xls'):
            book = xlrd.open_workbook(file_contents=uploaded.stream.read())
            sheet = book.sheet_by_index(0)

            def cell(r, c):
                try:
                    return sheet.cell_value(r - 1, c - 1)
                except IndexError:
                    return None

            raw_date = cell(2, 1)
        else:
            wb = load_workbook(uploaded.stream, data_only=True)
            sheet = wb.active

            def cell(r, c):
                return sheet.cell(row=r, column=c).value

            raw_date = cell(2, 1)

        if raw_date:
            if isinstance(raw_date, datetime):
                report_date = raw_date.date().isoformat()
            elif isinstance(raw_date, date):
                report_date = raw_date.isoformat()
            elif isinstance(raw_date, str):
                try:
                    report_date = datetime.strptime(raw_date.strip(), "%m/%d/%Y").date().isoformat()
                except ValueError:
                    pass
    except Exception as exc:
        abort(400, description=f'Failed to read Excel file: {exc}')

    rows = []
    row_idx = 7
    while True:
        model = cell(row_idx, 2)
        if model in (None, ''):
            row_idx += 1
            continue
        if str(model).strip().lower() == 'total':
            break
        rows.append({
            'Model Name': model,
            'Total Boards': cell(row_idx, 3) or 0,
            'Total Parts/Board': cell(row_idx, 4) or 0,
            'Total Parts': cell(row_idx, 5) or 0,
            'NG Parts': cell(row_idx, 6) or 0,
            'NG PPM': cell(row_idx, 7) or 0,
            'FalseCall Parts': cell(row_idx, 8) or 0,
            'FalseCall PPM': cell(row_idx, 9) or 0,
            'Report Date': report_date,
            'Line': line,
        })
        row_idx += 1

    if not rows:
        return jsonify({'inserted': 0}), 200

    _, error = insert_moat_bulk(rows)
    if error:
        abort(500, description=error)

    return jsonify({'inserted': len(rows)}), 201


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


def _yield_preview(fetch_func):
    """Return yield percentages for the last 7 recorded days."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    data, error = fetch_func()
    if error:
        abort(500, description=error)

    from datetime import datetime, timedelta
    from collections import defaultdict

    def parse_date(d):
        if not d:
            return None
        try:
            return datetime.fromisoformat(str(d)).date()
        except Exception:
            return None

    today = datetime.utcnow().date()
    start = today - timedelta(days=6)
    agg = defaultdict(lambda: {'accepted': 0, 'rejected': 0})

    for row in data:
        d = parse_date(row.get('Date') or row.get('date'))
        if not d or d < start or d > today:
            continue
        inspected = int(row.get('Quantity Inspected') or row.get('quantity_inspected') or 0)
        rejected = int(row.get('Quantity Rejected') or row.get('quantity_rejected') or 0)
        accepted = inspected - rejected
        if accepted < 0:
            accepted = 0
        agg[d]['accepted'] += accepted
        agg[d]['rejected'] += rejected

    dates = sorted(agg.keys())
    yields = []
    for d in dates:
        a = agg[d]['accepted']
        r = agg[d]['rejected']
        tot = a + r
        y = (a / tot * 100) if tot else 0
        yields.append(y)

    avg_yield = sum(yields) / len(yields) if yields else 0
    start_date = dates[0].isoformat() if dates else None
    end_date = dates[-1].isoformat() if dates else None

    return jsonify({
        'labels': [d.isoformat() for d in dates],
        'yields': yields,
        'avg_yield': avg_yield,
        'start_date': start_date,
        'end_date': end_date,
    })


@main_bp.route('/aoi_preview', methods=['GET'])
def aoi_preview():
    return _yield_preview(fetch_aoi_reports)


@main_bp.route('/fi_preview', methods=['GET'])
def fi_preview():
    return _yield_preview(fetch_fi_reports)


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


@main_bp.route('/tools/assembly-forecast')
def assembly_forecast():
    """Render the Assembly Forecast tool page."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('assembly_forecast.html', username=session.get('username'))


@main_bp.route('/api/assemblies/search')
def api_assemblies_search():
    """Search distinct assembly names across MOAT and AOI data."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    q = (request.args.get('q') or '').strip().lower()
    assemblies: set[str] = set()
    moat_rows, moat_error = fetch_moat()
    if moat_error:
        abort(500, description=moat_error)
    for row in moat_rows or []:
        asm = (
            row.get('Assembly')
            or row.get('Model')
            or row.get('Model Name')
            or ''
        )
        if not asm:
            continue
        if q and q not in asm.lower():
            continue
        assemblies.add(asm)
    aoi_rows, aoi_error = fetch_aoi_reports()
    if aoi_error:
        abort(500, description=aoi_error)
    for row in aoi_rows or []:
        asm = row.get('Assembly') or row.get('aoi_Assembly') or ''
        if not asm:
            continue
        if q and q not in asm.lower():
            continue
        assemblies.add(asm)
    return jsonify(sorted(assemblies))


@main_bp.route('/api/assemblies/forecast', methods=['POST'])
def api_assemblies_forecast():
    """Return forecast metrics for selected assemblies."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    payload = request.get_json(silent=True) or {}
    assemblies = payload.get('assemblies') or []
    moat_rows, moat_error = fetch_moat()
    if moat_error:
        abort(500, description=moat_error)
    aoi_rows, aoi_error = fetch_aoi_reports()
    if aoi_error:
        abort(500, description=aoi_error)
    metrics = _aggregate_forecast(assemblies, moat_rows, aoi_rows)
    return jsonify({'assemblies': metrics})


def _fig_to_data_uri(fig):
    if plt is None:
        return ''
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')
    return f"data:image/png;base64,{b64}"


def _build_metrics_chart(info: dict) -> str:
    """Return a bar chart image for key assembly metrics as a data URI."""
    if plt is None:
        return ""
    labels = [
        "Yield",
        "Hist Yield",
        "AOI Rejects",
        "Past Rejects",
        "FI Rejects",
    ]
    values = [
        info.get("yield") or 0,
        info.get("pastAvg") if isinstance(info.get("pastAvg"), (int, float)) else 0,
        info.get("currentRejects") or 0,
        info.get("pastRejectsAvg") or 0,
        info.get("fiTypicalRejects") or 0,
    ]
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.bar(range(len(values)), values, color="steelblue")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6)
    ax.set_ylabel("Value")
    fig.tight_layout()
    return _fig_to_data_uri(fig)


def _compute_control_limits(values: list[float]) -> tuple[float, float, float]:
    """Return mean, UCL and LCL for ``values`` using ±3σ limits."""
    if not values:
        return 0.0, 0.0, 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    stdev = math.sqrt(variance)
    ucl = mean + 3 * stdev
    lcl = max(0.0, mean - 3 * stdev)
    return mean, ucl, lcl


def _build_assembly_moat_charts(assembly: str, moat_rows: list[dict]) -> dict[str, str]:
    """Build an overlay control chart for SMT and TH false-call data.

    Returns a dictionary with a single key ``overlayChart`` containing a
    data URI for the generated chart (or an empty string if unavailable).
    """
    if plt is None:
        return {"overlayChart": ""}

    records: list[dict[str, str | float]] = []
    asm_lower = assembly.lower()
    for row in moat_rows or []:
        model = (
            row.get("Model Name")
            or row.get("model_name")
            or row.get("Model")
            or ""
        )
        model_lower = str(model).lower()
        if asm_lower not in model_lower:
            continue
        try:
            fc = float(row.get("FalseCall Parts") or row.get("falsecall_parts") or 0)
            boards = float(row.get("Total Boards") or row.get("total_boards") or 0)
        except (TypeError, ValueError):
            continue
        if boards == 0:
            continue
        group = "th" if "th" in model_lower else "smt" if "smt" in model_lower else None
        if group is None:
            continue
        records.append(
            {
                "group": group,
                "date": row.get("Report Date") or row.get("report_date") or "",
                "val": fc / boards,
            }
        )

    # average values per day for each group
    grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"sum": 0.0, "count": 0})
    for rec in records:
        key = (rec["group"], rec["date"])
        grouped[key]["sum"] += rec["val"]
        grouped[key]["count"] += 1
    averaged_records = [
        {
            "group": g,
            "date": d,
            "val": info["sum"] / info["count"] if info["count"] else 0.0,
        }
        for (g, d), info in grouped.items()
    ]

    smt_data = [r for r in averaged_records if r["group"] == "smt"]
    th_data = [r for r in averaged_records if r["group"] == "th"]
    if not (smt_data or th_data):
        return {"overlayChart": ""}

    fig, ax = plt.subplots(figsize=(6, 3))
    groups = {
        "smt": {
            "data": smt_data,
            "color": "tab:blue",
            "label": "SMT",
        },
        "th": {
            "data": th_data,
            "color": "tab:orange",
            "label": "TH",
        },
    }
    for key, info in groups.items():
        data = info["data"]
        if not data:
            continue
        data.sort(key=lambda d: d.get("date", ""))
        dates = [d["date"] for d in data]
        vals = [d["val"] for d in data]
        mean, ucl, lcl = _compute_control_limits(vals)
        color = info["color"]
        label = info["label"]
        ax.plot(dates, vals, marker="o", color=color, label=f"{label} False Calls/Board")
        ax.axhline(mean, linestyle="--", color=color, label=f"{label} Mean")
        ax.axhline(ucl, linestyle="--", color=color, label=f"{label} +3σ")
        ax.axhline(lcl, linestyle="--", color=color, label=f"{label} -3σ")

    ax.set_ylabel("False Calls/Board")
    ax.set_title("SMT vs TH False Calls Control Chart")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))

    return {"overlayChart": _fig_to_data_uri(fig)}


def _generate_report_charts(payload):
    if plt is None:
        return {
            'yieldTrendImg': '',
            'operatorRejectImg': '',
            'modelFalseCallsImg': '',
            'fcVsNgRateImg': '',
            'fcNgRatioImg': '',
        }
    charts: dict[str, str] = {}

    # Yield trend chart
    fig, ax = plt.subplots(figsize=(8, 4))
    dates = payload.get('yieldData', {}).get('dates', [])
    yields = payload.get('yieldData', {}).get('yields', [])
    if dates and yields:
        ax.plot(dates, yields, marker='o')
        ax.set_xlabel('Date')
        ax.set_ylabel('Yield %')
        ax.set_title('Yield Trend')
        ax.tick_params(axis='x', rotation=45)
    charts['yieldTrendImg'] = _fig_to_data_uri(fig)

    # Operator reject chart (stacked bar)
    fig, ax = plt.subplots(figsize=(8, 4))
    ops = payload.get('operators', [])
    if ops:
        names = [o['name'] for o in ops]
        accepted = [o['inspected'] - o['rejected'] for o in ops]
        rejected = [o['rejected'] for o in ops]
        ax.bar(names, accepted, label='Accepted')
        ax.bar(names, rejected, bottom=accepted, label='Rejected')
        ax.set_ylabel('Boards')
        ax.set_title('Operator Rejects')
        ax.tick_params(axis='x', rotation=45)
        ax.legend()
    charts['operatorRejectImg'] = _fig_to_data_uri(fig)

    # Model false calls chart with control limits
    fig, ax = plt.subplots(figsize=(8, 4))
    models = payload.get('models', [])
    if models:
        labels = [m['name'] for m in models]
        vals = [m['falseCalls'] for m in models]
        ax.plot(labels, vals, marker='o', color='orange', label='False Calls')
        mean = sum(vals) / len(vals)
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
        upper = mean + 3 * std
        lower = max(mean - 3 * std, 0)
        ax.plot(labels, [mean] * len(labels), linestyle='--', color='blue', label='Mean')
        ax.plot(labels, [upper] * len(labels), linestyle='--', color='green', label='+3σ')
        ax.plot(labels, [lower] * len(labels), linestyle='--', color='red', label='-3σ')
        ax.set_ylabel('False Calls/Board')
        ax.set_title('False Calls by Model')
        ax.tick_params(axis='x', labelbottom=False)
        ax.legend()
    charts['modelFalseCallsImg'] = _fig_to_data_uri(fig)

    # FC vs NG rate chart
    fig, ax = plt.subplots(figsize=(8, 4))
    fc_vs_ng = payload.get('fcVsNgRate', {})
    dates = fc_vs_ng.get('dates', [])
    ng_ppm = fc_vs_ng.get('ngPpm', [])
    fc_ppm = fc_vs_ng.get('fcPpm', [])
    if dates:
        ax.plot(dates, ng_ppm, color='red', label='NG PPM')
        ax.plot(dates, fc_ppm, color='blue', label='FalseCall PPM')
        ax.set_ylabel('PPM')
        ax.set_title('FC vs NG Rate')
        ax.tick_params(axis='x', rotation=45)
        ax.legend()
    charts['fcVsNgRateImg'] = _fig_to_data_uri(fig)

    # FC/NG ratio chart
    fig, ax = plt.subplots(figsize=(8, 4))
    fc_ng = payload.get('fcNgRatio', {})
    models = fc_ng.get('models', [])
    ratios = fc_ng.get('ratios', [])
    if models:
        ax.bar(models, ratios, color='teal')
        ax.set_ylabel('FC/NG Ratio')
        ax.set_title('FC/NG Ratio by Model')
        ax.tick_params(axis='x', labelbottom=False)
    charts['fcNgRatioImg'] = _fig_to_data_uri(fig)

    return charts


def _generate_operator_report_charts(payload):
    """Generate charts for the operator report.

    This now produces a single chart with boards inspected as bars and
    reject rates as a line on a secondary y-axis.
    """
    if plt is None:
        return {"dailyImg": ""}

    charts: dict[str, str] = {}

    daily = payload.get("daily", {})
    dates = daily.get("dates", [])
    inspected = daily.get("inspected", [])
    rates = daily.get("rejectRates", [])

    fig, ax = plt.subplots(figsize=(8, 4))
    ax2 = ax.twinx()

    if dates and inspected:
        ax.bar(dates, inspected, color="steelblue", label="Boards Inspected")
        ax.set_ylabel("Boards Inspected")
    if dates and rates:
        ax2.plot(dates, rates, marker="o", color="crimson", label="Reject %")
        ax2.set_ylabel("Reject %")

    ax.set_xlabel("Date")
    ax.set_title("Daily Reject Rate and Boards Inspected")
    ax.tick_params(axis="x", rotation=45)

    lines, labels = [], []
    for a in (ax, ax2):
        l, lab = a.get_legend_handles_labels()
        lines.extend(l)
        labels.extend(lab)
    ax.legend(lines, labels, loc="best")

    charts["dailyImg"] = _fig_to_data_uri(fig)

    return charts


def _generate_aoi_daily_report_charts(payload):
    """Generate charts for the AOI daily report.

    Creates a simple bar chart showing the total quantity inspected for
    1st and 2nd shift.
    """
    s1 = payload.get("shift1_total")
    s2 = payload.get("shift2_total")
    s1 = s1 if s1 is not None else payload.get("shiftTotals", {}).get("shift1", {}).get("inspected", 0)
    s2 = s2 if s2 is not None else payload.get("shiftTotals", {}).get("shift2", {}).get("inspected", 0)
    s1_pct = payload.get("shift1_reject_pct")
    s2_pct = payload.get("shift2_reject_pct")
    s1_pct = s1_pct if s1_pct is not None else payload.get("shiftTotals", {}).get("shift1", {}).get("rejectRate", 0)
    s2_pct = s2_pct if s2_pct is not None else payload.get("shiftTotals", {}).get("shift2", {}).get("rejectRate", 0)

    if s1 > s2:
        diff = s1 - s2
        desc = f"1st shift inspected {diff} more boards than 2nd shift"
        pct_diff = s1_pct - s2_pct
        if pct_diff > 0:
            desc += f" and had a reject rate {pct_diff:.2f} percentage points higher."
        elif pct_diff < 0:
            desc += f" and had a reject rate {abs(pct_diff):.2f} percentage points lower."
        else:
            desc += " and had the same reject rate."
    elif s2 > s1:
        diff = s2 - s1
        desc = f"2nd shift inspected {diff} more boards than 1st shift"
        pct_diff = s2_pct - s1_pct
        if pct_diff > 0:
            desc += f" and had a reject rate {pct_diff:.2f} percentage points higher."
        elif pct_diff < 0:
            desc += f" and had a reject rate {abs(pct_diff):.2f} percentage points lower."
        else:
            desc += " and had the same reject rate."
    else:
        desc = "Both shifts inspected the same number of boards"
        pct_diff = s1_pct - s2_pct
        if pct_diff > 0:
            desc += f", but 1st shift's reject rate was {pct_diff:.2f} percentage points higher."
        elif pct_diff < 0:
            desc += f", but 2nd shift's reject rate was {abs(pct_diff):.2f} percentage points higher."
        else:
            desc += " and had the same reject rate."

    if plt is None:
        return {"shiftImg": "", "shiftImgDesc": desc}

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["1st", "2nd"], [s1, s2], color="steelblue")
    ax.set_ylabel("Boards Inspected")
    ax.set_title("Boards Inspected by Shift")

    charts: dict[str, str] = {}
    charts["shiftImg"] = _fig_to_data_uri(fig)
    charts["shiftImgDesc"] = desc
    return charts


def build_report_payload(start=None, end=None):
    """Aggregate yield, operator and false-call stats for the AOI integrated report.

    This function now merges AOI report rows that have not yet been
    incorporated into ``combined_reports`` so the AOI Integrated Report can
    surface newly uploaded AOI data without waiting for the combined table
    to refresh.
    """
    combined, error = fetch_combined_reports()
    if error:
        current_app.logger.error("Combined report fetch failed: %s", error)

    phrases = current_app.config.get('NON_AOI_PHRASES', [])
    from collections import defaultdict

    by_date = defaultdict(lambda: {'inspected': 0.0, 'aoi_rej': 0.0, 'fi_rej': 0.0})
    by_assembly = defaultdict(lambda: {'inspected': 0.0, 'aoi_rej': 0.0, 'fi_rej': 0.0})
    # Track job numbers found in combined data so we can avoid double counting
    combined_jobs: set[str | None] = set()

    for row in combined or []:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue

        inspected = float(row.get('aoi_Quantity Inspected') or row.get('Quantity Inspected') or 0)
        aoi_rej = float(row.get('aoi_Quantity Rejected') or row.get('Quantity Rejected') or 0)

        fi_rej_val = row.get('fi_Quantity Rejected')
        try:
            fi_rej = float(fi_rej_val)
        except (TypeError, ValueError):
            fi_rej = 0.0
        if fi_rej == 0.0:
            info = row.get('fi_Additional Information') or row.get('fi_Add Info') or ''
            fi_rej = parse_fi_rejections(info, phrases)

        assembly = row.get('aoi_Assembly') or row.get('Assembly') or 'Unknown'
        job_number = row.get('aoi_Job Number') or row.get('Job Number')

        by_date[dt]['inspected'] += inspected
        by_date[dt]['aoi_rej'] += aoi_rej
        by_date[dt]['fi_rej'] += fi_rej

        by_assembly[assembly]['inspected'] += inspected
        by_assembly[assembly]['aoi_rej'] += aoi_rej
        by_assembly[assembly]['fi_rej'] += fi_rej

        combined_jobs.add(job_number)

    # Operator statistics now come from AOI reports exclusively, and we also
    # merge any AOI-only rows into the by_date/by_assembly aggregations above.
    aoi_reports, error = fetch_aoi_reports()
    if error:
        abort(500, description=error)

    by_operator = defaultdict(lambda: {'inspected': 0.0, 'rejected': 0.0})
    for row in aoi_reports or []:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue

        inspected = float(row.get('aoi_Quantity Inspected') or row.get('Quantity Inspected') or 0)
        rejected = float(row.get('aoi_Quantity Rejected') or row.get('Quantity Rejected') or 0)
        operator = row.get('aoi_Operator') or row.get('Operator') or 'Unknown'
        by_operator[operator]['inspected'] += inspected
        by_operator[operator]['rejected'] += rejected

        job_number = row.get('aoi_Job Number') or row.get('Job Number')
        # Only augment yield statistics if this job was absent from combined_reports
        if job_number not in combined_jobs:
            assembly = row.get('aoi_Assembly') or row.get('Assembly') or 'Unknown'
            by_date[dt]['inspected'] += inspected
            by_date[dt]['aoi_rej'] += rejected
            by_assembly[assembly]['inspected'] += inspected
            by_assembly[assembly]['aoi_rej'] += rejected
            combined_jobs.add(job_number)

    dates = sorted(d for d in by_date.keys() if d)
    yields = []
    for d in dates:
        vals = by_date[d]
        rej = vals['aoi_rej'] + vals['fi_rej']
        y = ((vals['inspected'] - rej) / vals['inspected'] * 100.0) if vals['inspected'] else 0.0
        yields.append(y)

    assembly_yields = {}
    for asm, vals in by_assembly.items():
        rej = vals['aoi_rej'] + vals['fi_rej']
        assembly_yields[asm] = ((vals['inspected'] - rej) / vals['inspected'] * 100.0) if vals['inspected'] else 0.0

    operator_rows = [
        {
            'name': op,
            'inspected': vals['inspected'],
            'rejected': vals['rejected'],
        }
        for op, vals in by_operator.items()
    ]

    moat, error = fetch_moat()
    if error:
        abort(500, description=error)
    model_group = defaultdict(lambda: {'fc': 0.0, 'boards': 0.0})
    fc_vs_ng = defaultdict(lambda: {'ng': 0.0, 'fc': 0.0, 'parts': 0.0})
    fc_ng_ratio = defaultdict(lambda: {'fc': 0.0, 'ng': 0.0})
    for row in moat or []:
        dt = _parse_date(row.get('Report Date') or row.get('report_date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        model = (
            row.get('Model')
            or row.get('model')
            or row.get('Model Name')
            or row.get('model_name')
            or 'Unknown'
        )
        fc = float(row.get('FalseCall Parts') or row.get('falsecall_parts') or 0)
        boards = float(row.get('Total Boards') or row.get('total_boards') or 0)
        model_group[model]['fc'] += fc
        model_group[model]['boards'] += boards

        parts = float(row.get('Total Parts') or row.get('total_parts') or 0)
        ng_parts_val = row.get('NG Parts') or row.get('ng_parts')
        if ng_parts_val is not None:
            try:
                ng_parts = float(ng_parts_val)
            except (TypeError, ValueError):
                ng_parts = 0.0
        else:
            ng_ppm_val = (
                row.get('NG PPM')
                or row.get('ng_ppm')
                or row.get('NG_PPM')
                or 0
            )
            try:
                ng_ppm = float(ng_ppm_val)
            except (TypeError, ValueError):
                ng_ppm = 0.0
            ng_parts = (parts * ng_ppm) / 1_000_000 if parts and ng_ppm else 0.0
        ag = fc_vs_ng[dt]
        ag['ng'] += ng_parts
        ag['fc'] += fc
        ag['parts'] += parts

        fc_ng_ratio[model]['fc'] += fc
        fc_ng_ratio[model]['ng'] += ng_parts

    model_rows = []
    for model, vals in model_group.items():
        fc_per_board = (vals['fc'] / vals['boards']) if vals['boards'] else 0.0
        model_rows.append({'name': model, 'falseCalls': fc_per_board})

    combined_ratios = []
    for model, vals in fc_ng_ratio.items():
        ng_val = vals['ng']
        if ng_val <= 2:
            continue
        ratio = (vals['fc'] / ng_val) if ng_val else 0.0
        combined_ratios.append(
            {'model': model, 'fc': vals['fc'], 'ng': ng_val, 'ratio': ratio}
        )
    combined_ratios.sort(key=lambda x: x['ratio'], reverse=True)
    top_ratios = combined_ratios[:10]
    fc_ng_ratio_data = {
        'models': [t['model'] for t in top_ratios],
        'fcParts': [t['fc'] for t in top_ratios],
        'ngParts': [t['ng'] for t in top_ratios],
        'ratios': [t['ratio'] for t in top_ratios],
    }
    fc_ng_ratio_summary = {
        'top': [{'name': t['model'], 'ratio': t['ratio']} for t in combined_ratios[:3]]
    }

    fc_vs_ng_dates = sorted(d for d in fc_vs_ng.keys() if d)
    ng_ppm_series: list[float] = []
    fc_ppm_series: list[float] = []
    for d in fc_vs_ng_dates:
        vals = fc_vs_ng[d]
        parts = vals['parts']
        ng_ppm_series.append((vals['ng'] / parts * 1_000_000) if parts else 0.0)
        fc_ppm_series.append((vals['fc'] / parts * 1_000_000) if parts else 0.0)

    # Correlation and trend for FC vs NG
    n = min(len(ng_ppm_series), len(fc_ppm_series))
    if n > 1:
        avg_ng = sum(ng_ppm_series) / n
        avg_fc = sum(fc_ppm_series) / n
        num = sum((ng_ppm_series[i] - avg_ng) * (fc_ppm_series[i] - avg_fc) for i in range(n))
        den_ng = sum((ng_ppm_series[i] - avg_ng) ** 2 for i in range(n))
        den_fc = sum((fc_ppm_series[i] - avg_fc) ** 2 for i in range(n))
        corr = num / math.sqrt(den_ng * den_fc) if den_ng and den_fc else 0.0
        fc_trend = (
            'increased'
            if fc_ppm_series[0] < fc_ppm_series[-1]
            else 'decreased' if fc_ppm_series[0] > fc_ppm_series[-1] else 'stable'
        )
    else:
        corr = 0.0
        fc_trend = 'stable'
    fc_vs_ng_summary = {'correlation': corr, 'fcTrend': fc_trend}

    # --- Precompute summaries -------------------------------------------------
    if yields:
        avg_yield = sum(yields) / len(yields)
        worst_idx = min(range(len(yields)), key=lambda i: yields[i])
        worst_day = {
            'date': dates[worst_idx].isoformat(),
            'yield': yields[worst_idx],
        }
    else:
        avg_yield = 0.0
        worst_day = {'date': None, 'yield': 0.0}

    if assembly_yields:
        worst_asm = min(assembly_yields.items(), key=lambda item: item[1])
        worst_assembly = {'assembly': worst_asm[0], 'yield': worst_asm[1]}
    else:
        worst_assembly = {'assembly': None, 'yield': 0.0}

    yield_summary = {
        'avg': avg_yield,
        'worstDay': worst_day,
        'worstAssembly': worst_assembly,
    }

    ops = []
    for op in operator_rows:
        inspected = op['inspected']
        rate = (op['rejected'] / inspected * 100.0) if inspected else 0.0
        ops.append({**op, 'rate': rate})

    total_boards = sum(o['inspected'] for o in operator_rows)
    avg_rate = sum(o['rate'] for o in ops) / len(ops) if ops else 0.0
    num_ops = len(ops)
    avg_boards = total_boards / num_ops if num_ops else 0.0
    if ops:
        min_op = min(ops, key=lambda o: o['rate'])
        max_op = max(ops, key=lambda o: o['rate'])
    else:
        min_op = max_op = {'name': None, 'rate': 0.0}

    operator_summary = {
        'totalBoards': total_boards,
        'avgRate': avg_rate,
        'min': {'name': min_op['name'], 'rate': min_op['rate']},
        'max': {'name': max_op['name'], 'rate': max_op['rate']},
        'avgBoards': avg_boards,
    }

    avg_fc = sum(m['falseCalls'] for m in model_rows) / len(model_rows) if model_rows else 0.0
    problem_assemblies = [m for m in model_rows if m['falseCalls'] > 20]
    model_summary = {
        'avgFalseCalls': avg_fc,
        'over20': [m['name'] for m in problem_assemblies],
    }
    dates_iso = [d.isoformat() for d in dates]
    yield_pairs = list(zip(dates_iso, yields))

    fc_vs_ng_dates_iso = [d.isoformat() for d in fc_vs_ng_dates]
    fc_vs_ng_pairs = list(zip(fc_vs_ng_dates_iso, ng_ppm_series, fc_ppm_series))

    fc_ng_ratio_pairs = list(
        zip(
            fc_ng_ratio_data['models'],
            fc_ng_ratio_data['fcParts'],
            fc_ng_ratio_data['ngParts'],
            fc_ng_ratio_data['ratios'],
        )
    )

    # Centralized targets for key metrics so deltas can be computed uniformly
    targets = {
        'avg_yield': 98.0,
        'operator_rate': 5.0,
        'false_calls': 10.0,
    }

    def _kpi(label, value, target_key):
        item = {'label': label, 'value': value}
        target = targets.get(target_key)
        if target is not None:
            item['target'] = target
            item['delta'] = value - target
        return item

    summary_kpis = [
        _kpi('Average Yield', yield_summary['avg'], 'avg_yield'),
        _kpi('Operator Defect Rate', operator_summary['avgRate'], 'operator_rate'),
        _kpi('False Calls per Board', model_summary['avgFalseCalls'], 'false_calls'),
    ]

    summary_actions = [
        {'label': m['name'], 'value': m['falseCalls']}
        for m in problem_assemblies
    ]

    top_risks = [
        _kpi(asm, assembly_yields[asm], 'avg_yield')
        for asm, _ in sorted(assembly_yields.items(), key=lambda x: x[1])[:3]
    ]

    summary_charts = [
        {'label': 'Yield Trend', 'data': yield_pairs},
        {'label': 'FC vs NG', 'data': fc_vs_ng_pairs},
    ]

    executive_summary = {
        'kpis': summary_kpis,
        'actions': summary_actions,
        'topRisks': top_risks,
        'charts': summary_charts,
    }

    highlights = summary_actions
    kpis = summary_kpis

    charts = {
        'yield': yield_pairs,
        'fcVsNg': fc_vs_ng_pairs,
        'fcNgRatio': fc_ng_ratio_pairs,
    }

    top_tables = {
        'operators': ops,
        'models': model_rows,
    }

    jobs = [
        {'label': op['name'], 'value': op['inspected']} for op in ops
    ]

    appendix = {
        'yield': yield_pairs,
        'fcVsNg': fc_vs_ng_pairs,
        'fcNgRatio': fc_ng_ratio_pairs,
    }

    return {
        'yieldData': {
            'dates': dates_iso,
            'yields': yields,
            'assemblyYields': assembly_yields,
        },
        'yield_pairs': yield_pairs,
        'operators': ops,
        'models': model_rows,
        'fcVsNgRate': {
            'dates': fc_vs_ng_dates_iso,
            'ngPpm': ng_ppm_series,
            'fcPpm': fc_ppm_series,
        },
        'fc_vs_ng_pairs': fc_vs_ng_pairs,
        'fcVsNgSummary': fc_vs_ng_summary,
        'fcNgRatio': fc_ng_ratio_data,
        'fc_ng_ratio_pairs': fc_ng_ratio_pairs,
        'fcNgRatioSummary': fc_ng_ratio_summary,
        'yieldSummary': yield_summary,
        'operatorSummary': operator_summary,
        'modelSummary': model_summary,
        'problemAssemblies': problem_assemblies,
        'summary_kpis': summary_kpis,
        'summary_actions': summary_actions,
        'top_risks': top_risks,
        'summary_charts': summary_charts,
        'executive_summary': executive_summary,
        'highlights': highlights,
        'kpis': kpis,
        'charts': charts,
        'top_tables': top_tables,
        'jobs': jobs,
        'avgBoards': avg_boards,
        'appendix': appendix,
    }


@main_bp.route('/api/reports/integrated', methods=['GET'])
def api_integrated_report():
    """Aggregate yield, operator and false-call stats for the AOI integrated report."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))

    payload = build_report_payload(start, end)
    return jsonify(payload)


@main_bp.route('/reports/integrated', methods=['GET'])
def integrated_report():
    """Render the AOI Integrated Report page."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('integrated_report.html', username=session.get('username'))


@main_bp.route('/reports/integrated/export')
def export_integrated_report():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    start_str = start.strftime('%y%m%d') if start else ''
    end_str = end.strftime('%y%m%d') if end else ''
    payload = build_report_payload(start, end)
    payload['start'] = start.isoformat() if start else ''
    payload['end'] = end.isoformat() if end else ''
    charts = _generate_report_charts(payload)
    body = request.get_json(silent=True) or {}

    def _get(name, default=''):
        return request.args.get(name, body.get(name, default))

    def _get_bool(name, default=True):
        value = request.args.get(name)
        if value is None:
            value = body.get(name)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).lower() not in {'0', 'false', 'no'}

    show_cover = _get_bool('show_cover', False)
    show_summary = _get_bool('show_summary')
    title = _get('title')
    subtitle = _get('subtitle')
    report_date = _get('report_date')
    period = _get('period')
    author = _get('author')
    logo_url = _get('logo_url')
    footer_left = _get('footer_left')
    report_id = _get('report_id')
    contact = _get('contact', 'tschwartz@4spectra.com')
    confidentiality = _get('confidentiality', 'Spectra-Tech • Confidential')
    generated_at = datetime.now(ZoneInfo('EST')).strftime('%Y-%m-%d %H:%M:%S %Z')

    if show_summary:
        payload.setdefault(
            'yieldSummary',
            {
                'avg': 0.0,
                'worstDay': {'date': None, 'yield': 0.0},
                'worstAssembly': {'assembly': None, 'yield': 0.0},
            },
        )
        payload.setdefault('operatorSummary', payload.get('summary', {}))
        payload.setdefault('modelSummary', {'avgFalseCalls': 0.0})

    html = render_template(
        'report/integrated/index.html',
        show_cover=show_cover,
        show_summary=show_summary,
        title=title,
        subtitle=subtitle,
        report_date=report_date,
        period=period,
        author=author,
        logo_url=logo_url,
        footer_left=footer_left,
        report_id=report_id,
        contact=contact,
        confidentiality=confidentiality,
        generated_at=generated_at,
        **payload,
        **charts,
    )
    fmt = request.args.get('format')
    if fmt == 'pdf':
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        font_config = FontConfiguration()
        pdf = HTML(string=html, base_url=request.url_root).write_pdf(font_config=font_config)
        filename = f"{start_str}_{end_str}_aoiIR.pdf"
        return send_file(
            io.BytesIO(pdf),
            mimetype='application/pdf',
            download_name=filename,
            as_attachment=True,
        )
    if fmt == 'html':
        return send_file(
            io.BytesIO(html.encode('utf-8')),
            mimetype='text/html',
            download_name='report.html',
            as_attachment=True,
        )
    return html


@main_bp.route('/reports/aoi_daily', methods=['GET'])
def aoi_daily_report_page():
    """Render the AOI Daily Report page."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('aoi_daily_report.html', username=session.get('username'))


@main_bp.route('/reports/aoi_daily/export')
def export_aoi_daily_report():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    day = _parse_date(request.args.get('date'))
    if not day:
        abort(400, description='Invalid date')

    operator = request.args.get('operator') or None
    assembly = request.args.get('assembly') or None

    start = end = day.isoformat()
    generated_at = datetime.now(ZoneInfo('EST')).strftime('%Y-%m-%d %H:%M:%S %Z')
    contact = request.args.get('contact', 'tschawtz@4spectra.com')

    payload = build_aoi_daily_report_payload(day, operator, assembly)
    charts = _generate_aoi_daily_report_charts(payload)
    payload.update(charts)

    show_cover = str(request.args.get('show_cover', 'false')).lower() not in {'0', 'false', 'no'}
    html = render_template(
        'report/aoi_daily/index.html',
        day=day.isoformat(),
        show_cover=show_cover,
        start=start,
        end=end,
        generated_at=generated_at,
        contact=contact,
        **payload,
    )

    fmt = request.args.get('format')
    if fmt == 'pdf':
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        font_config = FontConfiguration()
        pdf = HTML(string=html, base_url=request.url_root).write_pdf(font_config=font_config)
        filename = f"{day.strftime('%y%m%d')}_aoi_daily_report.pdf"
        return send_file(
            io.BytesIO(pdf),
            mimetype='application/pdf',
            download_name=filename,
            as_attachment=True,
        )
    if fmt == 'html':
        return send_file(
            io.BytesIO(html.encode('utf-8')),
            mimetype='text/html',
            download_name='report.html',
            as_attachment=True,
        )
    return html


def _aggregate_operator_report(start=None, end=None, operator: str | None = None):
    """Aggregate AOI report rows for the operator report."""
    from collections import defaultdict

    # Normalize operator filter to a set of lowercase names
    operators = {
        o.strip().lower() for o in (operator or '').split(',') if o.strip()
    }

    rows, error = fetch_aoi_reports()
    if error:
        abort(500, description=error)

    daily = defaultdict(lambda: {'inspected': 0.0, 'rejected': 0.0})
    assemblies = defaultdict(lambda: {'inspected': 0.0, 'rejected': 0.0})
    total_inspected = 0.0
    total_rejected = 0.0
    unique_ops: set[str] = set()

    for row in rows or []:
        date_val = _parse_date(row.get('Date') or row.get('aoi_Date'))
        if start and date_val and date_val < start:
            continue
        if end and date_val and date_val > end:
            continue

        op_name = (row.get('Operator') or row.get('aoi_Operator') or '').strip()
        if operators and op_name.lower() not in operators:
            continue
        if op_name:
            unique_ops.add(op_name)

        inspected = float(
            row.get('Quantity Inspected')
            or row.get('quantity_inspected')
            or row.get('aoi_Quantity Inspected')
            or 0
        )
        rejected = float(
            row.get('Quantity Rejected')
            or row.get('quantity_rejected')
            or row.get('aoi_Quantity Rejected')
            or 0
        )

        if date_val:
            daily[date_val]['inspected'] += inspected
            daily[date_val]['rejected'] += rejected

        asm = row.get('Assembly') or row.get('aoi_Assembly') or 'Unknown'
        assemblies[asm]['inspected'] += inspected
        assemblies[asm]['rejected'] += rejected

        total_inspected += inspected
        total_rejected += rejected

    dates_sorted = sorted(daily.keys())
    daily_dates = [d.isoformat() for d in dates_sorted]
    daily_inspected = [daily[d]['inspected'] for d in dates_sorted]
    daily_reject_rates = [
        (daily[d]['rejected'] / daily[d]['inspected'] * 100)
        if daily[d]['inspected']
        else 0
        for d in dates_sorted
    ]

    num_days = len(dates_sorted)
    avg_per_shift = total_inspected / num_days if num_days else 0
    avg_reject_rate = (
        (total_rejected / total_inspected) * 100 if total_inspected else 0
    )
    num_ops = len(unique_ops)
    avg_boards = total_inspected / num_ops if num_ops else 0

    combined, error = fetch_combined_reports()
    if error:
        abort(500, description=error)

    fi_data = defaultdict(lambda: {'fi_rejected': 0.0, 'aoi_inspected': 0.0})
    for row in combined or []:
        date_val = _parse_date(row.get('aoi_Date') or row.get('Date'))
        if start and date_val and date_val < start:
            continue
        if end and date_val and date_val > end:
            continue

        op_name = (row.get('aoi_Operator') or row.get('Operator') or '').strip()
        if operators and op_name.lower() not in operators:
            continue

        asm = row.get('aoi_Assembly') or row.get('Assembly') or 'Unknown'
        fi_data[asm]['fi_rejected'] += float(row.get('fi_Quantity Rejected') or 0)
        fi_data[asm]['aoi_inspected'] += float(
            row.get('aoi_Quantity Inspected')
            or row.get('Quantity Inspected')
            or 0
        )

    assemblies_list = []
    for asm, counts in sorted(
        assemblies.items(), key=lambda x: x[1]['inspected'], reverse=True
    ):
        fi_info = fi_data.get(asm)
        if fi_info and fi_info['aoi_inspected']:
            fi_rate = fi_info['fi_rejected'] / fi_info['aoi_inspected'] * 100
        else:
            fi_rate = None
        assemblies_list.append(
            {
                'assembly': asm,
                'inspected': counts['inspected'],
                'rejected': counts['rejected'],
                'fiRejectRate': fi_rate,
            }
        )

    return {
        'daily': {
            'dates': daily_dates,
            'inspected': daily_inspected,
            'rejectRates': daily_reject_rates,
        },
        'summary': {
            'totalBoards': total_inspected,
            'avgPerShift': avg_per_shift,
            'avgRejectRate': avg_reject_rate,
            'avgBoards': avg_boards,
        },
        'assemblies': assemblies_list,
    }


@main_bp.route('/api/reports/operator', methods=['GET'])
def api_operator_report():
    """Return operator report data filtered by date range and operator."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    operator = request.args.get('operator') or None

    payload = _aggregate_operator_report(start, end, operator)
    return jsonify(payload)


def build_operator_report_payload(start=None, end=None, operator: str | None = None):
    """Build the operator report payload for export."""
    return _aggregate_operator_report(start, end, operator)


@main_bp.route('/api/reports/aoi_daily', methods=['GET'])
def api_aoi_daily_report():
    """Return AOI daily report data for preview."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    day = _parse_date(request.args.get('date'))
    if not day:
        abort(400, description='Invalid date')

    operator = request.args.get('operator') or None
    assembly = request.args.get('assembly') or None

    payload = build_aoi_daily_report_payload(day, operator, assembly)
    return jsonify(payload)


def build_aoi_daily_report_payload(
    day: date, operator: str | None = None, assembly: str | None = None
):
    """Build the AOI daily report payload for a specific day."""
    rows, error = fetch_aoi_reports()
    if error:
        abort(500, description=error)
    fi_rows, fi_error = fetch_fi_reports()
    if fi_error:
        abort(500, description=fi_error)

    op_filter = (
        {o.strip().lower() for o in operator.split(',') if o.strip()}
        if operator
        else None
    )
    asm_filter = (
        {a.strip().lower() for a in assembly.split(',') if a.strip()}
        if assembly
        else None
    )

    shift_rows = {"shift1": [], "shift2": []}
    shift_totals = {
        "shift1": {"inspected": 0, "rejected": 0},
        "shift2": {"inspected": 0, "rejected": 0},
    }
    assemblies: dict[str, dict[str, int | set]] = {}

    for row in rows or []:
        dt = _parse_date(row.get("Date") or row.get("date"))
        if not dt or dt != day:
            continue

        raw_shift = str(row.get("Shift") or "").lower()
        if raw_shift in {"1", "1st", "first", "shift 1", "shift1", "1st shift"}:
            shift_key = "shift1"
        elif raw_shift in {"2", "2nd", "second", "shift 2", "shift2", "2nd shift"}:
            shift_key = "shift2"
        else:
            continue

        op_name = row.get("Operator") or "Unknown"
        asm_name = row.get("Assembly") or "Unknown"
        program = row.get("Program") or "Unknown"
        if op_filter and op_name.lower() not in op_filter:
            continue
        if asm_filter and asm_name.lower() not in asm_filter:
            continue

        inspected = int(row.get("Quantity Inspected") or 0)
        rejected = int(row.get("Quantity Rejected") or 0)

        entry = {
            "operator": op_name,
            "program": program,
            "assembly": asm_name,
            "job": row.get("Job Number") or "",
            "inspected": inspected,
            "rejected": rejected,
        }
        shift_rows[shift_key].append(entry)
        shift_totals[shift_key]["inspected"] += inspected
        shift_totals[shift_key]["rejected"] += rejected

        assemblies.setdefault(
            asm_name,
            {"inspected": 0, "rejected": 0, "operators": set()},
        )
        assemblies[asm_name]["inspected"] += inspected
        assemblies[asm_name]["rejected"] += rejected
        assemblies[asm_name]["operators"].add(op_name)

    for info in shift_totals.values():
        ins = info["inspected"]
        rej = info["rejected"]
        info["rejectRate"] = (rej / ins * 100) if ins else 0

    # Aggregate FI typical rejects per assembly from historical FI data
    phrases = current_app.config.get("NON_AOI_PHRASES", [])
    fi_assembly: dict[str, list[int]] = defaultdict(list)
    for row in fi_rows or []:
        dt = _parse_date(row.get("Date") or row.get("date"))
        if not dt or dt >= day:
            continue
        asm = row.get("Assembly") or "Unknown"
        try:
            fi_rej = int(row.get("Quantity Rejected") or 0)
        except (TypeError, ValueError):
            fi_rej = 0
        if fi_rej == 0:
            info = row.get("Additional Information") or row.get("Add Info") or ""
            fi_rej = parse_fi_rejections(info, phrases)
        fi_assembly[asm].append(fi_rej)

    assembly_info = []
    for asm, vals in assemblies.items():
        ins = vals["inspected"]
        rej = vals["rejected"]
        today_yield = ((ins - rej) / ins * 100) if ins else 0

        # Past 4 job average yield and reject count
        past_rows = [
            r
            for r in rows or []
            if (r.get("Assembly") or "Unknown") == asm
            and (d := _parse_date(r.get("Date") or r.get("date")))
            and d < day
        ]
        job_groups: dict[str, dict[str, int | date | None]] = {}
        for r in past_rows:
            job = r.get("Job Number") or ""
            d = _parse_date(r.get("Date") or r.get("date"))
            g = job_groups.setdefault(
                job, {"inspected": 0, "rejected": 0, "date": d}
            )
            g["inspected"] += int(r.get("Quantity Inspected") or 0)
            g["rejected"] += int(r.get("Quantity Rejected") or 0)
            if d and (g["date"] is None or d > g["date"]):
                g["date"] = d

        jobs = sorted(
            job_groups.values(), key=lambda g: g.get("date") or date.min, reverse=True
        )
        yields: list[float] = []
        rejects: list[int] = []
        for g in jobs:
            i = g["inspected"]
            rj = g["rejected"]
            rejects.append(rj)
            if i:
                yields.append((i - rj) / i * 100)
        past_avg: float | str
        if yields:
            past_avg = sum(yields) / len(yields)
        else:
            past_avg = "first run"
        past_rej_avg = sum(rejects) / len(rejects) if rejects else 0

        fi_vals = fi_assembly.get(asm, [])
        fi_typical = sum(fi_vals) / len(fi_vals) if fi_vals else 0

        info = {
            "assembly": asm,
            "operators": sorted(vals.get("operators", set())),
            "boards": ins,
            "yield": today_yield,
            "pastAvg": past_avg,
            "currentRejects": rej,
            "pastRejectsAvg": past_rej_avg,
            "fiTypicalRejects": fi_typical,
        }
        info["metricsChart"] = _build_metrics_chart(info)
        assembly_info.append(info)
    moat_rows, moat_error = fetch_moat()
    if moat_error:
        current_app.logger.error("Failed to fetch MOAT data: %s", moat_error)
        moat_rows = []
    for asm in assembly_info:
        asm["overlayChart"] = _build_assembly_moat_charts(
            asm["assembly"], moat_rows
        ).get("overlayChart", "")

    # Compute overall shift summary statistics for template consumption
    s1_total = shift_totals["shift1"].get("inspected", 0)
    s2_total = shift_totals["shift2"].get("inspected", 0)
    s1_reject_pct = round(shift_totals["shift1"].get("rejectRate", 0), 2)
    s2_reject_pct = round(shift_totals["shift2"].get("rejectRate", 0), 2)
    shift_total_diff = abs(s1_total - s2_total)
    shift_reject_pct_diff = round(abs(s1_reject_pct - s2_reject_pct), 2)

    return {
        "date": day.isoformat(),
        "shift1": shift_rows["shift1"],
        "shift2": shift_rows["shift2"],
        "shiftTotals": shift_totals,
        "shift1_total": s1_total,
        "shift2_total": s2_total,
        "shift1_reject_pct": s1_reject_pct,
        "shift2_reject_pct": s2_reject_pct,
        "shift_total_diff": shift_total_diff,
        "shift_reject_pct_diff": shift_reject_pct_diff,
        "assemblies": assembly_info,
    }


@main_bp.route('/reports/operator', methods=['GET'])
def operator_report():
    """Render the Operator Report page."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('operator_report.html', username=session.get('username'))


@main_bp.route('/reports/operator/export')
def export_operator_report():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    operator = request.args.get('operator') or None

    start_str = start.strftime('%y%m%d') if start else ''
    end_str = end.strftime('%y%m%d') if end else ''

    payload = build_operator_report_payload(start, end, operator)
    payload['start'] = start.isoformat() if start else ''
    payload['end'] = end.isoformat() if end else ''

    combined, error = fetch_combined_reports()
    if error:
        current_app.logger.error("Combined report fetch failed: %s", error)

    charts = _generate_operator_report_charts(payload)
    payload.update(charts)

    body = request.get_json(silent=True) or {}

    def _get(name, default=''):
        return request.args.get(name, body.get(name, default))

    def _get_bool(name, default=True):
        value = request.args.get(name)
        if value is None:
            value = body.get(name)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).lower() not in {'0', 'false', 'no'}

    show_cover = _get_bool('show_cover', False)
    show_summary = _get_bool('show_summary')
    title = _get('title') or (operator or 'Operator Report')
    subtitle = _get('subtitle')
    report_date = _get('report_date')
    period = _get('period')
    author = _get('author')
    logo_url = _get('logo_url') or url_for('static', filename='images/company-logo.png')
    footer_left = _get('footer_left')
    report_id = _get('report_id')
    contact = _get('contact', 'tschwartz@4spectra.com')
    confidentiality = _get('confidentiality', 'Spectra-Tech • Confidential')
    generated_at = datetime.now(ZoneInfo('EST')).strftime('%Y-%m-%d %H:%M:%S %Z')

    if show_summary:
        payload.setdefault(
            'yieldSummary',
            {
                'avg': 0.0,
                'worstDay': {'date': None, 'yield': 0.0},
                'worstAssembly': {'assembly': None, 'yield': 0.0},
            },
        )
        payload.setdefault('operatorSummary', payload.get('summary', {}))
        payload.setdefault('modelSummary', {'avgFalseCalls': 0.0})

    html = render_template(
        'report/operator/index.html',
        show_cover=show_cover,
        show_summary=show_summary,
        title=title,
        subtitle=subtitle,
        report_date=report_date,
        period=period,
        author=author,
        logo_url=logo_url,
        footer_left=footer_left,
        report_id=report_id,
        contact=contact,
        confidentiality=confidentiality,
        generated_at=generated_at,
        operator=operator,
        **payload,
    )

    fmt = request.args.get('format')
    if fmt == 'pdf':
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        font_config = FontConfiguration()
        pdf = HTML(string=html, base_url=request.url_root).write_pdf(
            font_config=font_config
        )
        filename = f"{start_str}_{end_str}_operator_report.pdf"
        return send_file(
            io.BytesIO(pdf),
            mimetype='application/pdf',
            download_name=filename,
            as_attachment=True,
        )
    if fmt == 'html':
        return send_file(
            io.BytesIO(html.encode('utf-8')),
            mimetype='text/html',
            download_name='report.html',
            as_attachment=True,
        )
    return html


@main_bp.route('/analysis/aoi/grades', methods=['GET'])
def aoi_grades():
    """Return AOI grades computed from combined reports.

    Optional query parameters:
        - start_date
        - end_date
        - operators (comma-separated)
        - job_numbers (comma-separated)
    """
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    start = request.args.get('start_date')
    end = request.args.get('end_date')
    operators = request.args.get('operators', '')
    job_numbers = request.args.get('job_numbers', '')

    data, error = fetch_combined_reports()
    if error:
        abort(500, description=error)

    def to_set(values):
        return {v.strip() for v in values.split(',') if v.strip()}

    start_dt = _parse_date(start)
    end_dt = _parse_date(end)
    operator_set = to_set(operators)
    job_set = to_set(job_numbers)

    filtered = []
    for row in data:
        date_val = row.get('aoi_Date') or row.get('Date') or row.get('date')
        dt = _parse_date(date_val)
        if start_dt and (not dt or dt < start_dt):
            continue
        if end_dt and (not dt or dt > end_dt):
            continue
        operator = row.get('aoi_Operator') or row.get('Operator')
        if operator_set and (operator not in operator_set):
            continue
        job_number = row.get('aoi_Job Number') or row.get('Job Number')
        if job_set and (job_number not in job_set):
            continue
        info = row.get('fi_Additional Information') or ""
        phrases = current_app.config.get("NON_AOI_PHRASES", [])
        row['fi_Quantity Rejected'] = parse_fi_rejections(info, phrases)
        filtered.append(row)

    grades = calculate_aoi_grades(filtered)
    return jsonify(grades)


@main_bp.route('/analysis/aoi/grades/escape_pareto', methods=['GET'])
def aoi_grades_escape_pareto():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    group = request.args.get('group', 'model')  # 'model'|'operator'|'shift'
    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    data, error = fetch_combined_reports()
    if error:
        abort(500, description=error)

    key_map = {
        'model': lambda r: r.get('aoi_Assembly') or r.get('Model') or r.get('Assembly') or 'Unknown',
        'operator': lambda r: r.get('aoi_Operator') or r.get('Operator') or 'Unknown',
        'shift': lambda r: r.get('aoi_Shift') or r.get('Shift') or 'Unknown',
    }
    key_fn = key_map.get(group, key_map['model'])

    agg = defaultdict(lambda: {'fi_rej': 0.0, 'aoi_passed': 0.0})
    total_rej = 0.0

    for row in data:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        key = key_fn(row)
        passed = _aoi_passed(row)
        fi_rej = _fi_rejected(row)
        agg[key]['fi_rej'] += fi_rej
        agg[key]['aoi_passed'] += passed
        total_rej += fi_rej

    items = []
    for k, v in agg.items():
        denom = v['aoi_passed']
        rate = (1000.0 * v['fi_rej'] / denom) if denom else 0.0
        items.append({'key': k, 'fi_rej': v['fi_rej'], 'escape_rate_per_1k': rate})
    items.sort(key=lambda x: x['fi_rej'], reverse=True)

    cumulative = 0.0
    out = []
    for it in items:
        share = (it['fi_rej'] / total_rej) if total_rej else 0.0
        cumulative += share
        out.append({**it, 'cum_share': cumulative})
    return jsonify({'group': group, 'items': out, 'total_fi_rejects': total_rej})


@main_bp.route('/analysis/aoi/grades/gap_risk', methods=['GET'])
def aoi_grades_gap_risk():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    data, error = fetch_combined_reports()
    if error:
        abort(500, description=error)

    buckets = [
        (lambda d: d is not None and d <= 1, '≤1d'),
        (lambda d: d is not None and 2 <= d <= 3, '2–3d'),
        (lambda d: d is not None and 4 <= d <= 7, '4–7d'),
        (lambda d: d is None or d > 7, '>7d'),
    ]
    hist = Counter()
    fi_by_bucket = Counter()
    total_fi = 0.0
    phrases = current_app.config.get("NON_AOI_PHRASES", [])

    for row in data:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        gd = _gap_days(row)
        label = None
        for pred, name in buckets:
            if pred(gd):
                label = name
                break
        hist[label] += 1
        info = row.get('fi_Additional Information') or ""
        rej = parse_fi_rejections(info, phrases)
        fi_by_bucket[label] += rej
        total_fi += rej

    labels = ['≤1d', '2–3d', '4–7d', '>7d']
    return jsonify({
        'labels': labels,
        'histogram': [hist.get(l, 0) for l in labels],
        'fi_share': [ (fi_by_bucket.get(l, 0.0) / total_fi) if total_fi else 0.0 for l in labels ],
    })


@main_bp.route('/analysis/aoi/grades/learning_curves', methods=['GET'])
def aoi_grades_learning_curves():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    window = int(request.args.get('window', 10))
    op_filter = request.args.get('operators')
    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    data, error = fetch_combined_reports()
    if error:
        abort(500, description=error)

    per_op = defaultdict(list)
    job_totals = defaultdict(float)
    for row in data:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        job = row.get('aoi_Job Number') or row.get('Job Number') or 'Unknown'
        job_totals[job] += _aoi_passed(row)

    job_fi_rej = defaultdict(float)
    for row in data:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        job = row.get('aoi_Job Number') or row.get('Job Number') or 'Unknown'
        info = row.get('fi_Additional Information') or ""
        phrases = current_app.config.get("NON_AOI_PHRASES", [])
        rej = parse_fi_rejections(info, phrases)
        job_fi_rej[job] = max(job_fi_rej[job], rej)

    allowed = None
    if op_filter:
        allowed = {s.strip() for s in op_filter.split(',') if s.strip()}

    for row in data:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        op = row.get('aoi_Operator') or row.get('Operator') or 'Unknown'
        if allowed and op not in allowed:
            continue
        job = row.get('aoi_Job Number') or row.get('Job Number') or 'Unknown'
        passed = _aoi_passed(row)
        total = job_totals.get(job, 0.0)
        share = (passed / total) if total else 0.0
        attr_missed = share * job_fi_rej.get(job, 0.0)
        rate = (1000.0 * attr_missed / passed) if passed else 0.0
        if dt:
            per_op[op].append((dt, rate))

    out = {}
    for op, seq in per_op.items():
        seq.sort(key=lambda x: x[0])
        vals = [r for _, r in seq]
        dates = [d.isoformat() for d, _ in seq]
        roll = []
        for i in range(len(vals)):
            start_i = max(0, i - window + 1)
            sub = sorted(vals[start_i : i + 1])
            m = sub[len(sub)//2] if sub else 0.0
            roll.append(m)
        out[op] = { 'dates': dates, 'rates': vals, 'rolling_median': roll }

    return jsonify(out)


@main_bp.route('/analysis/aoi/grades/smt_th_heatmap', methods=['GET'])
def aoi_grades_smt_th_heatmap():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    data, error = fetch_combined_reports()
    if error:
        abort(500, description=error)

    # Buckets
    stations = set()
    parts = set()
    agg = defaultdict(lambda: {'fi_rej': 0.0, 'passed': 0.0})
    for row in data:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        station = row.get('aoi_Station') or row.get('Station') or 'Unknown'
        part = row.get('fi_Part Type') or row.get('fi_part_type') or 'Unknown'
        stations.add(station)
        parts.add(part)
        key = (station, part)
        agg[key]['fi_rej'] += _fi_rejected(row)
        agg[key]['passed'] += _aoi_passed(row)

    stations = sorted(stations)
    parts = sorted(parts)
    matrix = []
    for s in stations:
        row_vals = []
        for p in parts:
            v = agg.get((s, p), {'fi_rej': 0.0, 'passed': 0.0})
            rate = (1000.0 * v['fi_rej'] / v['passed']) if v['passed'] else 0.0
            row_vals.append(rate)
        matrix.append(row_vals)
    return jsonify({'stations': stations, 'part_types': parts, 'matrix': matrix})


@main_bp.route('/analysis/aoi/grades/shift_effect', methods=['GET'])
def aoi_grades_shift_effect():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    data, error = fetch_combined_reports()
    if error:
        abort(500, description=error)

    # Build per-record escape rate per 1k
    per_shift = defaultdict(list)
    per_weekday_shift = defaultdict(lambda: defaultdict(list))
    phrases = current_app.config.get("NON_AOI_PHRASES", [])
    for row in data:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        shift = row.get('aoi_Shift') or row.get('Shift') or 'Unknown'
        passed = _aoi_passed(row)
        info = row.get('fi_Additional Information') or ""
        rej = parse_fi_rejections(info, phrases)
        rate = (1000.0 * rej / passed) if passed else 0.0
        per_shift[shift].append(rate)
        if dt:
            wd = dt.weekday()  # 0=Mon
            per_weekday_shift[wd][shift].append(rate)

    # Summaries
    def _summary(xs):
        xs = sorted(xs)
        n = len(xs)
        if n == 0:
            return { 'n': 0, 'mean': 0, 'q1': 0, 'median': 0, 'q3': 0 }
        def q(p):
            k = int(p*(n-1))
            return xs[k]
        return {
            'n': n,
            'mean': sum(xs)/n,
            'q1': q(0.25),
            'median': q(0.5),
            'q3': q(0.75),
        }

    shift_labels = sorted(per_shift.keys())
    shift_stats = { s: _summary(per_shift[s]) for s in shift_labels }

    weekdays = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    heat = []
    all_shifts = sorted({s for d in per_weekday_shift.values() for s in d.keys()})
    for i in range(7):
        row_vals = []
        for s in all_shifts:
            xs = per_weekday_shift[i][s]
            v = (sum(xs)/len(xs)) if xs else 0.0
            row_vals.append(v)
        heat.append(row_vals)

    return jsonify({
        'shifts': shift_labels,
        'shift_stats': shift_stats,
        'weekday_labels': weekdays,
        'weekday_shifts': all_shifts,
        'weekday_heat': heat,
    })


@main_bp.route('/analysis/aoi/grades/customer_yield', methods=['GET'])
def aoi_grades_customer_yield():
    """Return per-customer true yield using AOI and FI rejects.

    True yield per customer = (AOI inspected - AOI rejected - FI rejected) / AOI inspected.
    """
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    data, error = fetch_combined_reports()
    if error:
        abort(500, description=error)

    from collections import defaultdict

    agg = defaultdict(lambda: {'inspected': 0.0, 'aoi_rej': 0.0, 'fi_rej': 0.0})
    label_map = {}
    for row in data:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        raw = (row.get('aoi_Customer') or row.get('Customer') or 'Unknown').strip()
        norm = raw.lower()
        label_map.setdefault(norm, raw)
        aoi_ins = float(row.get('aoi_Quantity Inspected') or row.get('Quantity Inspected') or 0)
        aoi_rej = float(row.get('aoi_Quantity Rejected') or row.get('Quantity Rejected') or 0)
        fi_rej = float(row.get('fi_Quantity Rejected') or 0)
        agg[norm]['inspected'] += aoi_ins
        agg[norm]['aoi_rej'] += aoi_rej
        agg[norm]['fi_rej'] += fi_rej

    items = []
    for norm, vals in agg.items():
        ins = vals['inspected']
        true_accepted = max(0.0, ins - vals['aoi_rej'] - vals['fi_rej'])
        yld = (true_accepted / ins * 100.0) if ins else 0.0
        items.append((label_map[norm], yld))

    # Sort by yield descending for readability
    items.sort(key=lambda x: x[1], reverse=True)
    return jsonify({
        'labels': [i[0] for i in items],
        'yields': [i[1] for i in items],
    })


@main_bp.route('/analysis/aoi/grades/program_trend', methods=['GET'])
def aoi_grades_program_trend():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    data, error = fetch_combined_reports()
    if error:
        abort(500, description=error)

    # Aggregate by model/rev and calendar month
    from collections import defaultdict
    agg = defaultdict(lambda: defaultdict(lambda: {'fi': 0.0, 'passed': 0.0}))
    phrases = current_app.config.get("NON_AOI_PHRASES", [])
    for row in data:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        model = row.get('aoi_Assembly') or row.get('Assembly') or 'Unknown'
        rev = row.get('aoi_Rev') or row.get('Rev') or ''
        key = f"{model} {rev}".strip()
        month = dt.replace(day=1).isoformat() if dt else 'Unknown'
        info = row.get('fi_Additional Information') or ""
        rej = parse_fi_rejections(info, phrases)
        agg[key][month]['fi'] += rej
        agg[key][month]['passed'] += _aoi_passed(row)

    # Build aligned series per key
    months = sorted({m for d in agg.values() for m in d.keys() if m != 'Unknown'})
    datasets = []
    for key, m in agg.items():
        data_points = []
        for mon in months:
            v = m.get(mon, {'fi': 0.0, 'passed': 0.0})
            rate = (1000.0 * v['fi'] / v['passed']) if v['passed'] else 0.0
            data_points.append(rate)
        datasets.append({'label': key, 'data': data_points})
    return jsonify({'months': months, 'datasets': datasets})


@main_bp.route('/analysis/aoi/grades/adjusted_operator_ranking', methods=['GET'])
def aoi_grades_adjusted_operator_ranking():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    import numpy as np
    start = _parse_date(request.args.get('start_date'))
    end = _parse_date(request.args.get('end_date'))
    data, error = fetch_combined_reports()
    if error:
        abort(500, description=error)

    rows = []
    phrases = current_app.config.get("NON_AOI_PHRASES", [])
    for row in data:
        dt = _parse_date(row.get('aoi_Date') or row.get('Date') or row.get('date'))
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt > end):
            continue
        op = row.get('aoi_Operator') or row.get('Operator') or 'Unknown'
        model = row.get('aoi_Assembly') or row.get('Assembly') or 'Unknown'
        shift = row.get('aoi_Shift') or row.get('Shift') or 'Unknown'
        passed = _aoi_passed(row)
        info = row.get('fi_Additional Information') or ""
        rej = parse_fi_rejections(info, phrases)
        y = (1000.0 * rej / passed) if passed else 0.0
        rows.append((op, model, shift, passed, y))

    if not rows:
        return jsonify({'operators': [], 'effects': []})

    # Build design matrix: intercept + model dummies + shift dummies + log(volume)
    ops = sorted({r[0] for r in rows})
    models = sorted({r[1] for r in rows})
    shifts = sorted({r[2] for r in rows})
    op_index = {k: i for i, k in enumerate(ops)}
    model_index = {k: i for i, k in enumerate(models)}
    shift_index = {k: i for i, k in enumerate(shifts)}

    n = len(rows)
    p = 1 + (len(models)-1) + (len(shifts)-1) + 1 + len(ops)  # intercept + effects + log(vol) + operator effects
    X = np.zeros((n, p))
    y = np.zeros(n)

    # Column layout
    col = 0
    intercept_col = col; col += 1
    model_cols = {m: intercept_col + 1 + i for i, m in enumerate(models[1:])}
    col = intercept_col + 1 + max(0, len(models)-1)
    shift_cols = {s: col + i for i, s in enumerate(shifts[1:])}
    col += max(0, len(shifts)-1)
    logv_col = col; col += 1
    op_cols = {o: col + i for i, o in enumerate(ops)}

    for i, (op, model, shift, passed, yi) in enumerate(rows):
        X[i, intercept_col] = 1.0
        if model in model_cols:
            X[i, model_cols[model]] = 1.0
        if shift in shift_cols:
            X[i, shift_cols[shift]] = 1.0
        X[i, logv_col] = np.log(max(passed, 1.0))
        X[i, op_cols[op]] = 1.0
        y[i] = yi

    # Ridge regularization for stability
    lam = 1.0
    XtX = X.T @ X + lam * np.eye(X.shape[1])
    Xty = X.T @ y
    beta = np.linalg.solve(XtX, Xty)

    effects = []
    for op in ops:
        eff = float(beta[op_cols[op]])
        # naive CI based on residual variance and count per operator
        idx = [i for i, r in enumerate(rows) if r[0] == op]
        resid = y[idx] - X[idx] @ beta
        var = float((resid @ resid) / max(1, len(idx)-1))
        se = (var ** 0.5) / (len(idx) ** 0.5)
        effects.append({'operator': op, 'effect': eff, 'lower': eff - 1.96*se, 'upper': eff + 1.96*se, 'n': len(idx)})

    # Sort best (lower effect is better) ascending
    effects.sort(key=lambda d: d['effect'])
    return jsonify({'operators': ops, 'effects': effects})


@main_bp.route('/analysis/aoi/grades/view', methods=['GET'])
def aoi_grades_page():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('aoi_grades.html', username=session.get('username'))


@main_bp.route('/analysis/aoi', methods=['GET'])
def aoi_daily_reports():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('aoi_daily_reports.html', username=session.get('username'))


def _daily_data(fetch_func):
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    job_numbers = request.args.get('job_numbers', '')
    rev_numbers = request.args.get('rev_numbers', '')
    assemblies = request.args.get('assemblies', '')
    customers = request.args.get('customers', '')
    operators = request.args.get('operators', '')

    data, error = fetch_func()
    if error:
        abort(500, description=error)

    from datetime import datetime
    from collections import defaultdict

    def parse_date(d):
        if not d:
            return None
        try:
            return datetime.fromisoformat(str(d)).date()
        except Exception:
            return None

    def to_list(s):
        return [x.strip() for x in s.split(',') if x.strip()]

    start_dt = parse_date(start)
    end_dt = parse_date(end)
    job_numbers = set(to_list(job_numbers))
    rev_numbers = set(to_list(rev_numbers))
    assemblies = set(to_list(assemblies))
    customers = set(x.lower() for x in to_list(customers))
    operators = set(to_list(operators))

    filtered = []
    for row in data:
        date = parse_date(row.get('Date') or row.get('date'))
        if start_dt and (not date or date < start_dt):
            continue
        if end_dt and (not date or date > end_dt):
            continue
        if job_numbers and (row.get('Job Number') not in job_numbers):
            continue
        if rev_numbers and (row.get('Rev') not in rev_numbers):
            continue
        if assemblies and (row.get('Assembly') not in assemblies):
            continue
        if customers and ((row.get('Customer') or '').lower() not in customers):
            continue
        if operators and (row.get('Operator') not in operators):
            continue
        filtered.append(row)

    view = request.args.get('view')

    if view == 'shift':
        agg = defaultdict(lambda: {'1st': {'accepted': 0, 'rejected': 0}, '2nd': {'accepted': 0, 'rejected': 0}})
        totals = {'1st': {'accepted': 0, 'rejected': 0}, '2nd': {'accepted': 0, 'rejected': 0}}
        for row in filtered:
            date = parse_date(row.get('Date') or row.get('date'))
            shift_raw = str(row.get('Shift') or row.get('shift') or '').lower()
            if shift_raw in ('1', '1st', 'first', 'shift 1', 'shift1', '1st shift'):
                shift = '1st'
            elif shift_raw in ('2', '2nd', 'second', 'shift 2', 'shift2', '2nd shift'):
                shift = '2nd'
            else:
                continue
            inspected = int(row.get('Quantity Inspected') or row.get('quantity_inspected') or 0)
            rejected = int(row.get('Quantity Rejected') or row.get('quantity_rejected') or 0)
            accepted = inspected - rejected
            if accepted < 0:
                accepted = 0
            agg[date][shift]['accepted'] += accepted
            agg[date][shift]['rejected'] += rejected
            totals[shift]['accepted'] += accepted
            totals[shift]['rejected'] += rejected

        dates = sorted(agg.keys())
        s1_acc = [agg[d]['1st']['accepted'] for d in dates]
        s1_rej = [agg[d]['1st']['rejected'] for d in dates]
        s2_acc = [agg[d]['2nd']['accepted'] for d in dates]
        s2_rej = [agg[d]['2nd']['rejected'] for d in dates]

        def avg_rate(tot):
            total = tot['accepted'] + tot['rejected']
            return (tot['rejected'] / total * 100) if total else 0

        return jsonify({
            'labels': [d.isoformat() for d in dates],
            'shift1': {'accepted': s1_acc, 'rejected': s1_rej, 'avg_reject_rate': avg_rate(totals['1st'])},
            'shift2': {'accepted': s2_acc, 'rejected': s2_rej, 'avg_reject_rate': avg_rate(totals['2nd'])},
        })

    if view == 'yield':
        agg = defaultdict(lambda: {'accepted': 0, 'rejected': 0})
        for row in filtered:
            date = parse_date(row.get('Date') or row.get('date'))
            inspected = int(row.get('Quantity Inspected') or row.get('quantity_inspected') or 0)
            rejected = int(row.get('Quantity Rejected') or row.get('quantity_rejected') or 0)
            accepted = inspected - rejected
            if accepted < 0:
                accepted = 0
            agg[date]['accepted'] += accepted
            agg[date]['rejected'] += rejected

        dates = sorted(agg.keys())
        yields = []
        for d in dates:
            a = agg[d]['accepted']
            r = agg[d]['rejected']
            tot = a + r
            y = (a / tot * 100) if tot else 0
            yields.append(y)
        avg_yield = sum(yields) / len(yields) if yields else 0
        min_yield = min(yields) if yields else 0
        max_yield = max(yields) if yields else 0
        return jsonify({
            'labels': [d.isoformat() for d in dates],
            'yields': yields,
            'avg_yield': avg_yield,
            'min_yield': min_yield,
            'max_yield': max_yield,
        })

    if view == 'customer_rate':
        agg = defaultdict(lambda: {'accepted': 0, 'rejected': 0})
        label_map = {}
        for row in filtered:
            raw = (row.get('Customer') or 'Unknown').strip()
            norm = raw.lower()
            label_map.setdefault(norm, raw)
            inspected = int(row.get('Quantity Inspected') or row.get('quantity_inspected') or 0)
            rejected = int(row.get('Quantity Rejected') or row.get('quantity_rejected') or 0)
            accepted = inspected - rejected
            if accepted < 0:
                accepted = 0
            agg[norm]['accepted'] += accepted
            agg[norm]['rejected'] += rejected

        items = []
        for norm, vals in agg.items():
            tot = vals['accepted'] + vals['rejected']
            rate = (vals['rejected'] / tot * 100) if tot else 0
            items.append((label_map[norm], rate))
        items.sort(key=lambda x: x[1], reverse=True)
        labels = [i[0] for i in items]
        rates = [i[1] for i in items]
        avg_rate = sum(rates) / len(rates) if rates else 0
        max_rate = max(rates) if rates else 0
        min_rate = min(rates) if rates else 0
        max_customer = labels[rates.index(max_rate)] if rates else ''
        min_customer = labels[rates.index(min_rate)] if rates else ''
        return jsonify({
            'labels': labels,
            'rates': rates,
            'avg_rate': avg_rate,
            'max_rate': max_rate,
            'max_customer': max_customer,
            'min_rate': min_rate,
            'min_customer': min_customer,
        })

    if view == 'assembly':
        agg = defaultdict(lambda: {'inspected': 0, 'rejected': 0})
        for row in filtered:
            asm = row.get('Assembly') or 'Unknown'
            inspected = int(row.get('Quantity Inspected') or row.get('quantity_inspected') or 0)
            rejected = int(row.get('Quantity Rejected') or row.get('quantity_rejected') or 0)
            agg[asm]['inspected'] += inspected
            agg[asm]['rejected'] += rejected

        items = []
        for asm, vals in agg.items():
            ins = vals['inspected']
            rej = vals['rejected']
            yld = ((ins - rej) / ins * 100) if ins else 0
            items.append((asm, ins, rej, yld))
        items.sort(key=lambda x: x[0])
        return jsonify({
            'assemblies': [i[0] for i in items],
            'inspected': [i[1] for i in items],
            'rejected': [i[2] for i in items],
            'yields': [i[3] for i in items],
        })

    agg = defaultdict(lambda: {'accepted': 0, 'rejected': 0})
    for row in filtered:
        op = row.get('Operator') or 'Unknown'
        inspected = int(row.get('Quantity Inspected') or row.get('quantity_inspected') or 0)
        rejected = int(row.get('Quantity Rejected') or row.get('quantity_rejected') or 0)
        accepted = inspected - rejected
        if accepted < 0:
            accepted = 0
        agg[op]['accepted'] += accepted
        agg[op]['rejected'] += rejected

    items = sorted(agg.items(), key=lambda kv: kv[1]['accepted'] + kv[1]['rejected'], reverse=True)
    labels = [k for k, _ in items]
    accepted_vals = [v['accepted'] for _, v in items]
    rejected_vals = [v['rejected'] for _, v in items]

    return jsonify({'labels': labels, 'accepted': accepted_vals, 'rejected': rejected_vals})


@main_bp.route('/analysis/aoi/data', methods=['GET'])
def aoi_daily_data():
    return _daily_data(fetch_aoi_reports)


@main_bp.route('/analysis/fi', methods=['GET'])
def fi_daily_reports():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('fi_daily_reports.html', username=session.get('username'))


@main_bp.route('/analysis/fi/data', methods=['GET'])
def fi_daily_data():
    return _daily_data(fetch_fi_reports)


@main_bp.route('/analysis/fi/saved', methods=['GET', 'POST', 'PUT'])
def fi_saved_queries():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    if request.method == 'GET':
        data, error = fetch_saved_fi_queries()
        if error:
            abort(500, description=error)
        return jsonify(data)

    payload = request.get_json() or {}
    keys = ["name", "description", "start_date", "end_date", "params"]
    payload = {k: payload.get(k) for k in keys if k in payload}
    overwrite = request.method == 'PUT' or request.args.get('overwrite')
    if overwrite:
        name = payload.get('name')
        data, error = update_saved_fi_query(name, payload)
        status = 200
    else:
        data, error = insert_saved_fi_query(payload)
        status = 201
    if error:
        abort(500, description=error)
    return jsonify(data), status


@main_bp.route('/analysis/aoi/saved', methods=['GET', 'POST', 'PUT'])
def aoi_saved_queries():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    if request.method == 'GET':
        data, error = fetch_saved_aoi_queries()
        if error:
            abort(500, description=error)
        return jsonify(data)

    payload = request.get_json() or {}
    keys = ["name", "description", "start_date", "end_date", "params"]
    payload = {k: payload.get(k) for k in keys if k in payload}
    overwrite = request.method == 'PUT' or request.args.get('overwrite')
    if overwrite:
        name = payload.get('name')
        data, error = update_saved_aoi_query(name, payload)
        status = 200
    else:
        data, error = insert_saved_aoi_query(payload)
        status = 201
    if error:
        abort(500, description=error)
    return jsonify(data), status
