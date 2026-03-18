"""OpenWeatherMap forecast client (consumer-local copy)."""

from __future__ import annotations

from datetime import datetime

import httpx

from models import DayForecast, WeatherContext

_BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"
_TIMEOUT = 10.0


def _bucket_by_day(items: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for item in items:
        day = item["dt_txt"][:10]
        buckets.setdefault(day, []).append(item)
    return buckets


def _summarise_day(items: list[dict]) -> DayForecast:
    temps = [i["main"]["temp"] for i in items]
    humidities = [i["main"]["humidity"] for i in items]
    winds = [i["wind"]["speed"] for i in items]
    conditions = [i["weather"][0]["main"] for i in items]
    condition = max(set(conditions), key=conditions.count)
    return DayForecast(
        temp=round(sum(temps) / len(temps), 1),
        condition=condition,
        humidity=round(sum(humidities) / len(humidities)),
        wind_speed=round(sum(winds) / len(winds), 1),
    )


def _build_summary(daily: dict[str, DayForecast]) -> str:
    parts: list[str] = []
    for day, fc in sorted(daily.items()):
        dt = datetime.strptime(day, "%Y-%m-%d")
        label = dt.strftime("%A")
        parts.append(f"{label}: {fc.condition}, {fc.temp}\u00b0C")
    return ". ".join(parts) + "."


async def fetch_weather(
    city: str,
    *,
    api_key: str | None = None,
) -> WeatherContext:
    """Fetch forecast for *city* and return a compact WeatherContext."""
    if not api_key:
        raise RuntimeError("Weather API key is required")

    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "cnt": 40,
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(_BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    buckets = _bucket_by_day(data["list"])
    daily = {day: _summarise_day(items) for day, items in buckets.items()}
    summary = _build_summary(daily)
    return WeatherContext(summary=summary, daily=daily)
