from flask import Flask

from .auth.routes import auth_bp
from .main.routes import main_bp


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.secret_key = "dev-secret-key"

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app
