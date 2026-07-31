import os

from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config
from .database import close_connection, init_db


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    config = Config()
    app.config.from_mapping(
        DATABASE=config.database_path,
        DEBUG=config.debug,
        TESTING=False,
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
    )

    if test_config is not None:
        app.config.update(test_config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as exc:
        app.logger.error("Could not create instance directory: %s", exc)

    with app.app_context():
        init_db(app)

    from .routes import api
    app.register_blueprint(api)

    from .ble_routes import ble_api
    app.register_blueprint(ble_api)

    CORS(app, origins=config.cors_origins, supports_credentials=False)

    _register_error_handlers(app)
    app.teardown_appcontext(close_connection)

    return app


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(exc):
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(404)
    def not_found(exc):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(exc):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_server_error(exc):
        return jsonify({"error": "Internal server error"}), 500
