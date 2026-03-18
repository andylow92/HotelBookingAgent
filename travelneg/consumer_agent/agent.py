"""Consumer-side agent logic.

Translates user preferences + live weather into scoring parameters
(weights and desired features) that the provider agent's scorer can use.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from travelneg.shared.models import DayForecast, WeatherContext, Weights


# ---------------------------------------------------------------------------
# Weather-based rules
# ---------------------------------------------------------------------------

# Conditions the OpenWeatherMap API returns as weather "main" values.
_BAD_WEATHER = {"Rain", "Drizzle", "Thunderstorm", "Snow"}
_HOT_WEATHER_THRESHOLD = 30.0  # °C
_COLD_WEATHER_THRESHOLD = 5.0  # °C
_WINDY_THRESHOLD = 10.0  # m/s


@dataclass
class WeatherAdjustment:
    """Describes how weather should shift weights and features."""

    weight_deltas: dict[str, float] = field(default_factory=dict)
    add_features: list[str] = field(default_factory=list)
    reason: str = ""


def analyse_weather(weather: WeatherContext) -> list[WeatherAdjustment]:
    """Inspect the forecast and return a list of adjustments to apply.

    Each rule is independent so they stack (rain + cold = indoor + heating).
    """
    if not weather.daily:
        return []

    forecasts = list(weather.daily.values())
    adjustments: list[WeatherAdjustment] = []

    # --- Rain / storm check (majority of days) ---
    rainy_days = sum(1 for f in forecasts if f.condition in _BAD_WEATHER)
    if rainy_days > len(forecasts) / 2:
        adjustments.append(WeatherAdjustment(
            weight_deltas={"match": 0.10, "location": -0.05},
            add_features=["indoor", "spa"],
            reason=f"Bad weather expected ({rainy_days}/{len(forecasts)} days) "
                   "— prioritising indoor amenities",
        ))

    # --- Heat check ---
    avg_temp = sum(f.temp for f in forecasts) / len(forecasts)
    if avg_temp >= _HOT_WEATHER_THRESHOLD:
        adjustments.append(WeatherAdjustment(
            weight_deltas={"match": 0.05},
            add_features=["pool", "air-conditioning"],
            reason=f"High temperatures expected (avg {avg_temp:.0f}°C) "
                   "— adding pool & AC preference",
        ))

    # --- Cold check ---
    if avg_temp <= _COLD_WEATHER_THRESHOLD:
        adjustments.append(WeatherAdjustment(
            weight_deltas={"match": 0.05, "location": 0.05},
            add_features=["heating", "indoor"],
            reason=f"Cold temperatures expected (avg {avg_temp:.0f}°C) "
                   "— preferring close & warm options",
        ))

    # --- Wind check ---
    windy_days = sum(
        1 for f in forecasts
        if f.wind_speed is not None and f.wind_speed >= _WINDY_THRESHOLD
    )
    if windy_days > len(forecasts) / 2:
        adjustments.append(WeatherAdjustment(
            add_features=["indoor"],
            reason=f"Windy conditions expected ({windy_days}/{len(forecasts)} days)",
        ))

    return adjustments


# ---------------------------------------------------------------------------
# Build the final scoring request
# ---------------------------------------------------------------------------

@dataclass
class ConsumerRequest:
    """Everything the provider agent needs to search and score options."""

    destination: str
    max_budget: float
    weights: Weights
    desired_features: list[str]
    weather_summary: str
    adjustments_applied: list[str]  # human-readable reasons


def build_request(
    *,
    destination: str,
    max_budget: float,
    desired_features: list[str] | None = None,
    base_weights: Weights | None = None,
    weather: WeatherContext | None = None,
) -> ConsumerRequest:
    """Combine user preferences with weather intelligence.

    Parameters
    ----------
    destination:
        City or area name.
    max_budget:
        Maximum price the user is willing to pay.
    desired_features:
        Features the user explicitly asked for (e.g. ["wifi", "pool"]).
    base_weights:
        User-supplied weight overrides.  Defaults to even weights.
    weather:
        Live weather forecast for the destination.  When provided the
        agent automatically adjusts weights and desired features.
    """
    weights = base_weights or Weights()
    features = list(desired_features or [])
    reasons: list[str] = []
    weather_summary = ""

    if weather:
        weather_summary = weather.summary
        adjustments = analyse_weather(weather)
        for adj in adjustments:
            reasons.append(adj.reason)
            # Merge added features (no duplicates)
            for feat in adj.add_features:
                if feat.lower() not in [f.lower() for f in features]:
                    features.append(feat)
            # Apply weight deltas
            for dim, delta in adj.weight_deltas.items():
                current = getattr(weights, dim)
                setattr(weights, dim, max(0.0, current + delta))

        # Re-normalise after all adjustments
        if adjustments:
            weights = weights.normalized()

    return ConsumerRequest(
        destination=destination,
        max_budget=max_budget,
        weights=weights,
        desired_features=features,
        weather_summary=weather_summary,
        adjustments_applied=reasons,
    )
