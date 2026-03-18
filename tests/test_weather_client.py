"""Tests for the weather client."""

import pytest
import httpx
import respx

from travelneg.consumer_agent.weather_client import fetch_weather
from travelneg.shared.models import WeatherContext


# Sample OpenWeatherMap response (minimal, 2 time slots across 2 days)
SAMPLE_OWM_RESPONSE = {
    "list": [
        {
            "dt_txt": "2026-03-19 12:00:00",
            "main": {"temp": 8.2, "humidity": 75},
            "weather": [{"main": "Rain"}],
            "wind": {"speed": 4.1},
        },
        {
            "dt_txt": "2026-03-19 15:00:00",
            "main": {"temp": 9.0, "humidity": 70},
            "weather": [{"main": "Rain"}],
            "wind": {"speed": 3.8},
        },
        {
            "dt_txt": "2026-03-20 12:00:00",
            "main": {"temp": 14.5, "humidity": 55},
            "weather": [{"main": "Clear"}],
            "wind": {"speed": 2.5},
        },
        {
            "dt_txt": "2026-03-20 15:00:00",
            "main": {"temp": 15.1, "humidity": 50},
            "weather": [{"main": "Clouds"}],
            "wind": {"speed": 2.0},
        },
    ]
}


@pytest.mark.asyncio
async def test_fetch_weather_parses_response():
    with respx.mock:
        respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(
            return_value=httpx.Response(200, json=SAMPLE_OWM_RESPONSE)
        )
        result = await fetch_weather("Berlin", api_key="test-key")

    assert isinstance(result, WeatherContext)
    assert "2026-03-19" in result.daily
    assert "2026-03-20" in result.daily

    day1 = result.daily["2026-03-19"]
    assert day1.condition == "Rain"
    assert day1.temp == pytest.approx(8.6, abs=0.1)

    day2 = result.daily["2026-03-20"]
    assert day2.condition in ("Clear", "Clouds")  # most frequent
    assert day2.temp == pytest.approx(14.8, abs=0.1)


@pytest.mark.asyncio
async def test_fetch_weather_summary_contains_days():
    with respx.mock:
        respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(
            return_value=httpx.Response(200, json=SAMPLE_OWM_RESPONSE)
        )
        result = await fetch_weather("Berlin", api_key="test-key")

    assert "Thursday" in result.summary  # 2026-03-19 is Thursday
    assert "Friday" in result.summary    # 2026-03-20 is Friday


@pytest.mark.asyncio
async def test_fetch_weather_raises_on_missing_key(monkeypatch):
    monkeypatch.delenv("WEATHER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="WEATHER_API_KEY"):
        await fetch_weather("Berlin")


@pytest.mark.asyncio
async def test_fetch_weather_raises_on_http_error():
    with respx.mock:
        respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(
            return_value=httpx.Response(401, json={"message": "Invalid API key"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_weather("Berlin", api_key="bad-key")
