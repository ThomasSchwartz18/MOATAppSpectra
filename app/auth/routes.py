import os

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

REQUIRED_USERS = {
    'USER': 'USER_PASSWORD',
    'ADMIN': 'ADMIN_PASSWORD',
}

USERS = {
    role: generate_password_hash(os.environ[env_key])
    for role, env_key in REQUIRED_USERS.items()
}

optional_employee_password = os.environ.get('EMPLOYEE_PASSWORD')
if optional_employee_password:
    USERS['EMPLOYEE'] = generate_password_hash(optional_employee_password)


@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        submitted_username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        normalized_username = submitted_username.upper()
        if (
            normalized_username in USERS
            and check_password_hash(USERS[normalized_username], password)
        ):
            session['username'] = submitted_username or normalized_username
            session['role'] = normalized_username
            return redirect(url_for('main.home'))
        flash('Invalid credentials.')
    return render_template('login.html', employee_enabled='EMPLOYEE' in USERS)


@auth_bp.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('auth.login'))
