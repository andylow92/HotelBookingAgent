"""Tests for the consumer agent weather-aware logic."""

import pytest

from travelneg.consumer_agent.agent import (
    analyse_weather,
    build_request,
    WeatherAdjustment,
)
from travelneg.shared.models import DayForecast, WeatherContext, Weights


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _weather(days: dict[str, tuple[str, float]]) -> WeatherContext:
    """Shorthand: {"Mon": ("Rain", 12.0)} → WeatherContext."""
    daily = {
        d: DayForecast(temp=temp, condition=cond, humidity=60, wind_speed=3.0)
        for d, (cond, temp) in days.items()
    }
    return WeatherContext(summary="test", daily=daily)


def _windy_weather(days: dict[str, tuple[str, float, float]]) -> WeatherContext:
    daily = {
        d: DayForecast(temp=temp, condition=cond, humidity=60, wind_speed=ws)
        for d, (cond, temp, ws) in days.items()
    }
    return WeatherContext(summary="test", daily=daily)


# ---------------------------------------------------------------------------
# analyse_weather
# ---------------------------------------------------------------------------

class TestAnalyseWeather:

    def test_clear_weather_no_adjustments(self):
        w = _weather({"Mon": ("Clear", 20), "Tue": ("Clear", 22)})
        assert analyse_weather(w) == []

    def test_rain_majority_triggers_indoor(self):
        w = _weather({
            "Mon": ("Rain", 14),
            "Tue": ("Rain", 13),
            "Wed": ("Clear", 18),
        })
        adjs = analyse_weather(w)
        assert len(adjs) == 1
        assert "indoor" in adjs[0].add_features
        assert "spa" in adjs[0].add_features
        assert "Bad weather" in adjs[0].reason

    def test_rain_minority_no_trigger(self):
        w = _weather({
            "Mon": ("Rain", 14),
            "Tue": ("Clear", 18),
            "Wed": ("Clear", 20),
        })
        assert analyse_weather(w) == []

    def test_hot_weather_adds_pool(self):
        w = _weather({"Mon": ("Clear", 33), "Tue": ("Clear", 35)})
        adjs = analyse_weather(w)
        features = [f for a in adjs for f in a.add_features]
        assert "pool" in features
        assert "air-conditioning" in features

    def test_cold_weather_adds_heating(self):
        w = _weather({"Mon": ("Clear", 2), "Tue": ("Clouds", 4)})
        adjs = analyse_weather(w)
        features = [f for a in adjs for f in a.add_features]
        assert "heating" in features
        assert "indoor" in features

    def test_cold_boosts_location_weight(self):
        w = _weather({"Mon": ("Clear", 0), "Tue": ("Clear", 3)})
        adjs = analyse_weather(w)
        location_deltas = [a.weight_deltas.get("location", 0) for a in adjs]
        assert sum(location_deltas) > 0

    def test_windy_adds_indoor(self):
        w = _windy_weather({
            "Mon": ("Clear", 20, 12.0),
            "Tue": ("Clear", 21, 15.0),
            "Wed": ("Clear", 19, 8.0),
        })
        adjs = analyse_weather(w)
        features = [f for a in adjs for f in a.add_features]
        assert "indoor" in features

    def test_empty_forecast_no_adjustments(self):
        w = WeatherContext(summary="", daily={})
        assert analyse_weather(w) == []

    def test_multiple_rules_stack(self):
        """Rain + cold should produce adjustments from both rules."""
        w = _weather({
            "Mon": ("Rain", 2),
            "Tue": ("Thunderstorm", 1),
            "Wed": ("Snow", 3),
        })
        adjs = analyse_weather(w)
        assert len(adjs) >= 2
        all_features = [f for a in adjs for f in a.add_features]
        assert "indoor" in all_features
        assert "heating" in all_features


# ---------------------------------------------------------------------------
# build_request
# ---------------------------------------------------------------------------

class TestBuildRequest:

    def test_basic_no_weather(self):
        req = build_request(
            destination="Berlin",
            max_budget=150,
            desired_features=["wifi"],
        )
        assert req.destination == "Berlin"
        assert req.max_budget == 150
        assert req.desired_features == ["wifi"]
        assert req.weather_summary == ""
        assert req.adjustments_applied == []

    def test_weather_adds_features(self):
        w = _weather({"Mon": ("Rain", 10), "Tue": ("Rain", 9), "Wed": ("Rain", 11)})
        req = build_request(
            destination="London",
            max_budget=200,
            desired_features=["wifi"],
            weather=w,
        )
        assert "wifi" in req.desired_features
        assert "indoor" in req.desired_features
        assert "spa" in req.desired_features

    def test_weather_no_duplicate_features(self):
        w = _weather({"Mon": ("Rain", 10), "Tue": ("Rain", 9)})
        req = build_request(
            destination="London",
            max_budget=200,
            desired_features=["indoor"],  # already has indoor
            weather=w,
        )
        indoor_count = sum(1 for f in req.desired_features if f.lower() == "indoor")
        assert indoor_count == 1

    def test_weather_adjusts_weights(self):
        w = _weather({"Mon": ("Rain", 10), "Tue": ("Rain", 9)})
        req = build_request(
            destination="Paris",
            max_budget=100,
            weather=w,
        )
        # match weight should have been boosted then normalized
        default_match = Weights().normalized().match
        assert req.weights.match > default_match

    def test_weights_still_normalized(self):
        w = _weather({"Mon": ("Rain", 2), "Tue": ("Snow", 1), "Wed": ("Rain", 3)})
        req = build_request(
            destination="Oslo",
            max_budget=300,
            weather=w,
        )
        total = (
            req.weights.price + req.weights.location + req.weights.rating
            + req.weights.flexibility + req.weights.match
        )
        assert total == pytest.approx(1.0)

    def test_clear_weather_preserves_original_weights(self):
        w = _weather({"Mon": ("Clear", 22), "Tue": ("Clear", 24)})
        original = Weights(price=0.30, location=0.20, rating=0.20, flexibility=0.15, match=0.15)
        req = build_request(
            destination="Lisbon",
            max_budget=120,
            base_weights=original,
            weather=w,
        )
        assert req.weights.price == pytest.approx(original.price)

    def test_weather_summary_included(self):
        w = WeatherContext(summary="Monday: Rain, 12°C.", daily={})
        req = build_request(destination="Berlin", max_budget=100, weather=w)
        assert req.weather_summary == "Monday: Rain, 12°C."

    def test_adjustment_reasons_captured(self):
        w = _weather({"Mon": ("Rain", 10), "Tue": ("Rain", 9)})
        req = build_request(destination="Berlin", max_budget=100, weather=w)
        assert len(req.adjustments_applied) > 0
        assert any("Bad weather" in r for r in req.adjustments_applied)
