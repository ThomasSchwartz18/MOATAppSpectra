import os
import json
from pathlib import Path

from flask import Flask, current_app
from supabase import create_client

from .auth.routes import auth_bp
from .main.routes import main_bp


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

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app


def get_supabase():
    return current_app.config["SUPABASE"]
