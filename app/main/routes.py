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
