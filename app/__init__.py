import os
import json
from pathlib import Path

from flask import Flask, current_app, session
from supabase import create_client

from .auth.routes import auth_bp
from .main.routes import main_bp
from .tracking import Tracker


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.secret_key = os.environ["SECRET_KEY"]

    supabase = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )
    app.config["SUPABASE"] = supabase
    app.config["SUPABASE_URL"] = os.environ["SUPABASE_URL"]

    phrases_path = (
        os.environ.get("NON_AOI_PHRASES_FILE")
        or Path(__file__).resolve().parent.parent / "config" / "non_aoi_phrases.json"
    )
    try:
        with open(phrases_path, "r", encoding="utf-8") as fh:
            app.config["NON_AOI_PHRASES"] = json.load(fh)
    except Exception:
        app.config["NON_AOI_PHRASES"] = []

    tracker_path = Path(app.instance_path) / "tracking.db"
    tracker = Tracker(tracker_path)
    app.config["TRACKER"] = tracker

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_user_context():
        username = session.get("username")
        role = session.get("role") or username
        tracking_session_id = session.get("tracking_session_id")
        return {
            "username": username,
            "user_role": role,
            "user_id": session.get("user_id"),
            "tracking_session_id": tracking_session_id,
        }

    return app


def get_supabase():
    return current_app.config["SUPABASE"]


def get_tracker() -> Tracker:
    return current_app.config["TRACKER"]
