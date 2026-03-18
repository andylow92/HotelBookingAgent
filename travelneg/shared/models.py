"""Pydantic models for structured messages between agents."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

class DayForecast(BaseModel):
    temp: float
    condition: str  # e.g. "Rain", "Clear", "Clouds"
    humidity: int | None = None
    wind_speed: float | None = None


class WeatherContext(BaseModel):
    summary: str
    daily: dict[str, DayForecast] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

class Coords(BaseModel):
    lat: float
    lon: float


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class Weights(BaseModel):
    price: float = 0.25
    location: float = 0.25
    rating: float = 0.20
    flexibility: float = 0.15
    match: float = 0.15

    def normalized(self) -> "Weights":
        total = self.price + self.location + self.rating + self.flexibility + self.match
        if total == 0:
            return Weights()
        return Weights(
            price=self.price / total,
            location=self.location / total,
            rating=self.rating / total,
            flexibility=self.flexibility / total,
            match=self.match / total,
        )


class ScoreBreakdown(BaseModel):
    price: float = 0.0
    location: float = 0.0
    rating: float = 0.0
    flexibility: float = 0.0
    match: float = 0.0


class ScoredOption(BaseModel):
    id: str
    name: str
    price: float
    rating: float = 0.0
    distance_km: float | None = None
    flexibility: str = "none"  # "free", "partial", "none"
    matched_features: list[str] = Field(default_factory=list)
    total_score: float = 0.0
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    tag: str = ""
    raw: dict = Field(default_factory=dict)  # original API response
