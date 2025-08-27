from flask import Blueprint, render_template, session, redirect, url_for

main_bp = Blueprint('main', __name__)


@main_bp.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('home.html', username=session.get('username'))
