import os

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
    app.secret_key = "dev-secret-key"

    supabase = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )
    app.config["SUPABASE"] = supabase

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app


def get_supabase():
    return current_app.config["SUPABASE"]
