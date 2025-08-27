from flask import Blueprint, render_template, session, redirect, url_for, abort
from functools import wraps

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
