from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class PredictionInterval:
    lower: int
    upper: int


@dataclass(frozen=True)
class OccupancyForecast:
    prediction_time: str
    forecast_time: str
    predicted_occupancy: int
    prediction_interval: PredictionInterval
    confidence: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class OvercrowdingForecast:
    predicted_occupancy: int
    room_capacity: int
    overcrowding_risk: bool
    risk_probability: float
    recommended_action: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EmptyRoomForecast:
    forecast_minutes: int
    empty_probability: float
    predicted_empty_duration_minutes: int
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
