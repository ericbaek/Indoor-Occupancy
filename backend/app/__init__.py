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
        ML_MODEL_DIR=config.ml_model_dir,
        ML_RECOMMENDATION_LOG_ENABLED=config.ml_recommendation_log_enabled,
        ML_LIVE_PREDICTION_ENABLED=config.ml_live_prediction_enabled,
        ML_LIVE_PREDICTION_INTERVAL_SECONDS=config.ml_live_prediction_interval_seconds,
        ML_SENSOR_WINDOW_SECONDS=config.ml_sensor_window_seconds,
        ML_ROOM_OPEN_HOUR=config.ml_room_open_hour,
        ML_ROOM_OPERATING_MINUTES=config.ml_room_operating_minutes,
        ML_DEFAULT_VENTILATION=config.ml_default_ventilation,
        ML_MINIMUM_VENTILATION=config.ml_minimum_ventilation,
        ML_MAXIMUM_VENTILATION=config.ml_maximum_ventilation,
        ML_RADAR_EXPECTED_INTERVAL_SECONDS=config.ml_radar_expected_interval_seconds,
        ML_CO2_EXPECTED_INTERVAL_SECONDS=config.ml_co2_expected_interval_seconds,
        ML_RADAR_STALE_SECONDS=config.ml_radar_stale_seconds,
        ML_CO2_STALE_SECONDS=config.ml_co2_stale_seconds,
        ML_BLE_LEFT_SCANNER_ID=config.ml_ble_left_scanner_id,
        ML_BLE_RIGHT_SCANNER_ID=config.ml_ble_right_scanner_id,
        ML_BLE_SWITCH_THRESHOLD_DB=config.ml_ble_switch_threshold_db,
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

    try:
        from ml.routes import ml_api
    except ModuleNotFoundError as exc:
        if exc.name != "ml":
            raise
        from backend.ml.routes import ml_api
    app.register_blueprint(ml_api)

    try:
        from ml.live_scheduler import start_live_prediction_scheduler
    except ModuleNotFoundError as exc:
        if exc.name != "ml":
            raise
        from backend.ml.live_scheduler import start_live_prediction_scheduler
    start_live_prediction_scheduler(app)

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
