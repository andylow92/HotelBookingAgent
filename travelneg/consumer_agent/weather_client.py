"""OpenWeatherMap forecast client.

Fetches a 5-day / 3-hour forecast and condenses it into a per-day summary
that fits neatly into the agent context (minimal tokens).

Requires the environment variable ``WEATHER_API_KEY``.
"""

from __future__ import annotations

import os
from datetime import datetime

import httpx

from travelneg.shared.models import DayForecast, WeatherContext

_BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"
_TIMEOUT = 10.0


def _get_api_key() -> str:
    key = os.environ.get("WEATHER_API_KEY", "")
    if not key:
        raise RuntimeError("WEATHER_API_KEY environment variable is not set")
    return key


def _bucket_by_day(items: list[dict]) -> dict[str, list[dict]]:
    """Group 3-hour forecast items by date string (YYYY-MM-DD)."""
    buckets: dict[str, list[dict]] = {}
    for item in items:
        day = item["dt_txt"][:10]  # "2026-03-19 12:00:00" → "2026-03-19"
        buckets.setdefault(day, []).append(item)
    return buckets


def _summarise_day(items: list[dict]) -> DayForecast:
    """Pick the most representative condition and average temp for a day."""
    temps = [i["main"]["temp"] for i in items]
    humidities = [i["main"]["humidity"] for i in items]
    winds = [i["wind"]["speed"] for i in items]
    # Most frequent weather condition wins
    conditions = [i["weather"][0]["main"] for i in items]
    condition = max(set(conditions), key=conditions.count)
    return DayForecast(
        temp=round(sum(temps) / len(temps), 1),
        condition=condition,
        humidity=round(sum(humidities) / len(humidities)),
        wind_speed=round(sum(winds) / len(winds), 1),
    )


def _build_summary(daily: dict[str, DayForecast]) -> str:
    """One-line-per-day summary for the LLM context."""
    parts: list[str] = []
    for day, fc in sorted(daily.items()):
        dt = datetime.strptime(day, "%Y-%m-%d")
        label = dt.strftime("%A")  # e.g. "Thursday"
        parts.append(f"{label}: {fc.condition}, {fc.temp}°C")
    return ". ".join(parts) + "."


async def fetch_weather(
    city: str,
    *,
    api_key: str | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> WeatherContext:
    """Fetch forecast for *city* and return a compact WeatherContext.

    Parameters
    ----------
    city:
        Destination city name (e.g. "Berlin").
    api_key:
        Override for the API key. Falls back to ``WEATHER_API_KEY`` env var.
    http_client:
        Optional pre-built httpx client (useful for testing / injection).
    """
    key = api_key or _get_api_key()
    params = {
        "q": city,
        "appid": key,
        "units": "metric",
        "cnt": 40,  # max 5 days of 3-hour intervals
    }

    client = http_client or httpx.AsyncClient(timeout=_TIMEOUT)
    should_close = http_client is None
    try:
        resp = await client.get(_BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    finally:
        if should_close:
            await client.aclose()

    buckets = _bucket_by_day(data["list"])
    daily = {day: _summarise_day(items) for day, items in buckets.items()}
    summary = _build_summary(daily)
    return WeatherContext(summary=summary, daily=daily)
