import os
from pathlib import Path


class Config:
    host: str = os.environ.get("FLASK_HOST", "0.0.0.0")
    port: int = int(os.environ.get("FLASK_PORT", "5000"))
    debug: bool = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    database_path: str = os.environ.get("DATABASE_PATH", "instance/occupancy.db")
    ml_model_dir: str = os.environ.get(
        "ML_MODEL_DIR",
        str(Path(__file__).resolve().parents[1] / "models" / "predictive_occupancy"),
    )
    ml_recommendation_log_enabled: bool = (
        os.environ.get("ML_RECOMMENDATION_LOG_ENABLED", "true").lower() == "true"
    )
    ml_live_prediction_enabled: bool = (
        os.environ.get("ML_LIVE_PREDICTION_ENABLED", "true").lower() == "true"
    )
    ml_live_prediction_interval_seconds: int = int(
        os.environ.get("ML_LIVE_PREDICTION_INTERVAL_SECONDS", "300")
    )
    ml_sensor_window_seconds: int = int(
        os.environ.get("ML_SENSOR_WINDOW_SECONDS", "300")
    )
    ml_room_open_hour: int = int(os.environ.get("ML_ROOM_OPEN_HOUR", "9"))
    ml_room_operating_minutes: int = int(
        os.environ.get("ML_ROOM_OPERATING_MINUTES", "480")
    )
    ml_default_ventilation: str = os.environ.get(
        "ML_DEFAULT_VENTILATION", "OFF"
    ).upper()
    ml_minimum_ventilation: str = os.environ.get(
        "ML_MINIMUM_VENTILATION", "OFF"
    ).upper()
    ml_maximum_ventilation: str = os.environ.get(
        "ML_MAXIMUM_VENTILATION", "HIGH"
    ).upper()
    ml_radar_expected_interval_seconds: float = float(
        os.environ.get("ML_RADAR_EXPECTED_INTERVAL_SECONDS", "1")
    )
    ml_co2_expected_interval_seconds: float = float(
        os.environ.get("ML_CO2_EXPECTED_INTERVAL_SECONDS", "5")
    )
    ml_radar_stale_seconds: float = float(
        os.environ.get("ML_RADAR_STALE_SECONDS", "15")
    )
    ml_co2_stale_seconds: float = float(
        os.environ.get("ML_CO2_STALE_SECONDS", "15")
    )
    ml_ble_left_scanner_id: str = os.environ.get(
        "ML_BLE_LEFT_SCANNER_ID", "anchor-left"
    )
    ml_ble_right_scanner_id: str = os.environ.get(
        "ML_BLE_RIGHT_SCANNER_ID", "anchor-right"
    )
    ml_ble_switch_threshold_db: float = float(
        os.environ.get("ML_BLE_SWITCH_THRESHOLD_DB", "5")
    )
    cors_origins: list[str] = [
        o.strip()
        for o in os.environ.get(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
        if o.strip()
    ]
