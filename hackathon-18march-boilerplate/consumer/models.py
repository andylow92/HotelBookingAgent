"""Pydantic models shared across the consumer agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DayForecast(BaseModel):
    temp: float
    condition: str
    humidity: int | None = None
    wind_speed: float | None = None


class WeatherContext(BaseModel):
    summary: str
    daily: dict[str, DayForecast] = Field(default_factory=dict)


class Coords(BaseModel):
    lat: float
    lon: float
