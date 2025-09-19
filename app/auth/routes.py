import os

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app import db as db_module

auth_bp = Blueprint('auth', __name__)

REQUIRED_USERS = {
    'USER': 'USER_PASSWORD',
    'ADMIN': 'ADMIN_PASSWORD',
}


def _load_environment_users() -> dict[str, str]:
    users = {
        role: generate_password_hash(os.environ[env_key])
        for role, env_key in REQUIRED_USERS.items()
        if os.environ.get(env_key)
    }
    optional_employee_password = os.environ.get('EMPLOYEE_PASSWORD')
    if optional_employee_password:
        users['EMPLOYEE'] = generate_password_hash(optional_employee_password)
    return users


ENVIRONMENT_USERS = _load_environment_users()


def _fetch_supabase_user(username: str) -> tuple[dict | None, str | None]:
    supabase = current_app.config.get('SUPABASE')
    if not supabase or not hasattr(supabase, 'table'):
        return None, None

    try:
        return db_module.fetch_app_user_credentials(username)
    except Exception as exc:  # pragma: no cover - defensive guard
        current_app.logger.warning("Failed to fetch Supabase credentials: %s", exc)
        return None, str(exc)


def _employee_login_enabled() -> bool:
    if 'EMPLOYEE' in ENVIRONMENT_USERS:
        return True

    try:
        records, error = db_module.fetch_app_users()
    except Exception:  # pragma: no cover - defensive guard
        return False

    if error or not records:
        return False

    for record in records:
        if (record.get('role') or '').upper() == 'EMPLOYEE':
            return True
    return False


@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        submitted_username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        normalized_username = submitted_username.upper()

        supabase_user = None
        supabase_error = None
        if submitted_username:
            supabase_user, supabase_error = _fetch_supabase_user(submitted_username)

        if supabase_user and supabase_user.get('password_hash'):
            if check_password_hash(supabase_user['password_hash'], password):
                session['user_id'] = supabase_user.get('id')
                session['username'] = (
                    supabase_user.get('display_name')
                    or supabase_user.get('username')
                    or submitted_username
                )
                session['role'] = (supabase_user.get('role') or 'USER').upper()
                return redirect(url_for('main.home'))
        elif supabase_error:
            flash(
                'Supabase user lookup failed; falling back to built-in credentials.',
                'warning',
            )

        if (
            normalized_username in ENVIRONMENT_USERS
            and check_password_hash(ENVIRONMENT_USERS[normalized_username], password)
        ):
            session['username'] = submitted_username or normalized_username
            session['role'] = normalized_username
            return redirect(url_for('main.home'))
        flash('Invalid credentials.')
    return render_template('login.html', employee_enabled=_employee_login_enabled())


@auth_bp.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    session.pop('user_id', None)
    return redirect(url_for('auth.login'))
