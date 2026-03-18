"""OpenWeatherMap forecast client.

Fetches a 5-day / 3-hour forecast and condenses it into a per-day summary
that fits neatly into the agent context (minimal tokens).
"""

import os
from datetime import datetime
import httpx

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
        day = item["dt_txt"][:10]
        buckets.setdefault(day, []).append(item)
    return buckets


def _summarise_day(items: list[dict]) -> dict:
    """Pick the most representative condition and average temp for a day."""
    temps = [i["main"]["temp"] for i in items]
    conditions = [i["weather"][0]["main"] for i in items]
    condition = max(set(conditions), key=conditions.count)
    return {
        "temp": round(sum(temps) / len(temps), 1),
        "condition": condition,
    }


def _build_summary(daily: dict[str, dict]) -> str:
    """One-line-per-day summary for the LLM context."""
    parts: list[str] = []
    for day, fc in sorted(daily.items()):
        dt = datetime.strptime(day, "%Y-%m-%d")
        label = dt.strftime("%A")
        parts.append(f"{label}: {fc['condition']}, {fc['temp']}°C")
    return ". ".join(parts) + "."


async def fetch_weather(
    city: str,
    *,
    api_key: str | None = None,
) -> dict:
    """Fetch forecast for *city* and return a compact weather context dict."""
    key = api_key or _get_api_key()
    params = {
        "q": city,
        "appid": key,
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
    return {"summary": summary, "daily": daily}
