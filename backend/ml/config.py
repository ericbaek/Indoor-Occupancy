from __future__ import annotations

from dataclasses import asdict, dataclass


RANDOM_SEED = 6733
MODEL_VERSION = "1.0.0"
DATASET_TYPE = "realistic_synthetic"
TIMEZONE = "Australia/Sydney"

TRAIN_START = "2026-07-20"
TRAIN_END = "2026-07-28"
VALIDATION_START = "2026-07-29"
VALIDATION_END = "2026-07-30"
TEST_START = "2026-07-31"
TEST_END = "2026-08-02"

OCCUPANCY_TARGET = "target_occupancy_plus_30m"
VENTILATION_TARGET = "target_ventilation_plus_30m"
OVERCROWDING_TARGET = "target_overcrowded_plus_30m"
EMPTY_30_SOURCE_TARGET = "target_occupancy_plus_30m"
EMPTY_60_SOURCE_TARGET = "target_occupancy_plus_60m"

FUTURE_TARGET_COLUMNS = (
    "target_occupancy_plus_15m",
    "target_occupancy_plus_30m",
    "target_occupancy_plus_60m",
    "target_co2_plus_30m_ppm",
    "target_ventilation_plus_30m",
    "target_overcrowded_plus_30m",
)

GROUND_TRUTH_COLUMNS = (
    "ground_truth_occupancy",
    "ground_truth_left_share",
    "ground_truth_dominant_side",
)

NUMERIC_FEATURES = (
    "day_of_week_num",
    "is_weekend",
    "hour",
    "minute",
    "minutes_since_open",
    "time_sin",
    "time_cos",
    "pir_entry_count",
    "pir_exit_count",
    "pir_net_count_change",
    "pir_event_count",
    "pir_entry_event_count",
    "pir_exit_event_count",
    "pir_total_detected_people",
    "pir_max_people_per_event",
    "pir_mean_duration_ms",
    "pir_cumulative_estimate",
    "radar_presence_ratio",
    "radar_mean_target_count",
    "radar_max_target_count",
    "radar_mean_abs_speed_cm_s",
    "radar_mean_distance_mm",
    "co2_mean_ppm",
    "co2_max_ppm",
    "co2_delta_ppm",
    "co2_rate_ppm_per_min",
    "temperature_mean_c",
    "humidity_mean_percent",
    "ble_left_rssi_mean_dbm",
    "ble_right_rssi_mean_dbm",
    "ble_left_right_rssi_diff_db",
    "ble_rssi_variance",
    "ble_signal_presence_ratio",
    "radar_missing_ratio",
    "co2_missing_ratio",
    "ble_missing_ratio",
    "radar_stale_flag",
)

CATEGORICAL_FEATURES = (
    "ventilation_current",
    "ble_dominant_side_estimate",
    "co2_quality_flag",
    "ble_quality_flag",
)

FEATURE_NAMES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
DERIVED_FORECAST_FEATURE = "predicted_occupancy_30m"

VENTILATION_LEVELS = ("OFF", "LOW", "MEDIUM", "HIGH")


@dataclass(frozen=True)
class TrainingConfig:
    random_seed: int = RANDOM_SEED
    room_capacity: int = 30
    prediction_cap_multiplier: float = 1.5
    minimum_confidence: float = 0.60
    empty_probability_threshold: float = 0.80
    co2_safety_override_ppm: float = 1400.0
    co2_energy_saving_max_ppm: float = 650.0
    co2_fast_rise_ppm_per_min: float = 3.0
    minimum_ventilation: str = "OFF"
    maximum_ventilation: str = "HIGH"
    prediction_interval_coverage: float = 0.90
    required_baseline_rmse_improvement: float = 0.10
    dry_run: bool = True

    @property
    def maximum_predicted_occupancy(self) -> int:
        return max(
            self.room_capacity,
            round(self.room_capacity * self.prediction_cap_multiplier),
        )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["maximum_predicted_occupancy"] = self.maximum_predicted_occupancy
        return data
