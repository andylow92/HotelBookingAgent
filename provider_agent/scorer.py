"""
Defensive scoring engine for hotel results.

Normalizes raw hotel data to 0–1 scores across 5 dimensions
(price, location, rating, cancellation, amenities), applies
user-defined weights, and ranks results with tags.

All scoring functions are defensive: division by zero, null values,
and invalid inputs produce valid neutral/fallback scores, not crashes.
"""

from __future__ import annotations

from shared.models import HotelOption, ScoreBreakdown, Weights

# ---------------------------------------------------------------------------
# Constants — sensible defaults for edge cases
# ---------------------------------------------------------------------------

DEFAULT_MAX_BUDGET = 500.0   # EUR — fallback when max_budget <= 0
DEFAULT_MAX_DISTANCE = 5.0   # km  — max distance for location scoring
DEFAULT_RATING = 3.0         # 3-star if rating is missing or invalid


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def clamp(value: float) -> float:
    """Ensure score stays in 0–1 range."""
    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# Individual dimension scoring functions
# ---------------------------------------------------------------------------

def calculate_price_score(price: float, max_budget: float) -> float:
    """Lower price → higher score (0–1).

    Edge cases:
    - max_budget <= 0 → use DEFAULT_MAX_BUDGET
    - price <= 0      → 0.5 (unknown = neutral)
    - price >= budget  → 0.0 (at or over budget = worst)
    """
    budget = max_budget if max_budget > 0 else DEFAULT_MAX_BUDGET
    if price <= 0:
        return 0.5  # Unknown price → neutral
    if price >= budget:
        return 0.0  # At or over budget → worst
    return clamp(1 - (price / budget))


def calculate_location_score(
    distance_km: float,
    max_distance: float = DEFAULT_MAX_DISTANCE,
) -> float:
    """Closer → higher score (0–1).

    Edge cases:
    - distance_km < 0      → 0.5 (unknown = neutral)
    - distance_km >= max    → 0.0 (too far = worst)
    """
    if distance_km < 0:
        return 0.5  # Unknown distance → neutral
    if distance_km >= max_distance:
        return 0.0  # Too far → worst
    return clamp(1 - (distance_km / max_distance))


def calculate_rating_score(rating: float | None) -> float:
    """Higher rating → higher score (out of 5.0).

    Edge cases:
    - rating is None or <= 0 → use DEFAULT_RATING (3.0)
    """
    r = rating if rating is not None and rating > 0 else DEFAULT_RATING
    return clamp(r / 5.0)


def calculate_cancellation_score(free_cancellation: bool) -> float:
    """Free cancellation = 1.0, else 0.0."""
    return 1.0 if free_cancellation else 0.0


def calculate_amenities_score(
    hotel_amenities: list[str],
    desired_amenities: list[str],
) -> float:
    """Fraction of desired amenities present in the hotel.

    Edge cases:
    - desired_amenities is empty → 1.0 (no requirements = full score)
    """
    if not desired_amenities:
        return 1.0  # No requirements → full score
    matched = len(set(hotel_amenities) & set(desired_amenities))
    return matched / len(desired_amenities)


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------

def score_hotel(
    hotel: dict,
    weights: Weights,
    max_budget: float,
    desired_amenities: list[str] | None = None,
) -> tuple[float, ScoreBreakdown]:
    """Score a single hotel with given weights.

    Args:
        hotel: Raw hotel dict with keys: price_per_night, distance_km,
               rating, free_cancellation, amenities.
        weights: User preference weights (auto-normalized to sum 1.0).
        max_budget: Maximum price per night from hard constraints.
        desired_amenities: List of amenities the user wants.

    Returns:
        (total_score, ScoreBreakdown) — both in 0–1 range.
    """
    desired = desired_amenities or []

    breakdown = ScoreBreakdown(
        price=calculate_price_score(
            hotel.get("price_per_night", 0), max_budget,
        ),
        location=calculate_location_score(
            hotel.get("distance_km", 0),
        ),
        rating=calculate_rating_score(
            hotel.get("rating"),
        ),
        cancellation=calculate_cancellation_score(
            hotel.get("free_cancellation", False),
        ),
        amenities=calculate_amenities_score(
            hotel.get("amenities", []), desired,
        ),
    )

    # Weighted sum
    total = (
        breakdown.price * weights.price
        + breakdown.location * weights.location
        + breakdown.rating * weights.rating
        + breakdown.cancellation * weights.cancellation
        + breakdown.amenities * weights.amenities
    )

    return clamp(total), breakdown


# ---------------------------------------------------------------------------
# Ranking & tagging
# ---------------------------------------------------------------------------

def _assign_tags(options: list[HotelOption]) -> list[HotelOption]:
    """Assign BEST_BALANCE, CHEAPEST, HIGHEST_RATED tags to top results.

    Rules:
    - #1 by total_score → BEST_BALANCE (always)
    - Cheapest among the group → CHEAPEST (if different from BEST_BALANCE)
    - Highest rated among the group → HIGHEST_RATED (if not already tagged)
    """
    if not options:
        return options

    # First: BEST_BALANCE is always the top-ranked option
    options[0].tag = "BEST_BALANCE"
    tagged_indices = {0}

    if len(options) > 1:
        # Find cheapest (lowest price_per_night) among remaining
        cheapest_idx = min(
            (i for i in range(len(options)) if i not in tagged_indices),
            key=lambda i: options[i].price_per_night,
        )
        options[cheapest_idx].tag = "CHEAPEST"
        tagged_indices.add(cheapest_idx)

    if len(options) > 2:
        # Find highest rated among remaining
        highest_rated_idx = max(
            (i for i in range(len(options)) if i not in tagged_indices),
            key=lambda i: options[i].rating,
        )
        options[highest_rated_idx].tag = "HIGHEST_RATED"

    return options


def score_and_rank(
    hotels: list[dict],
    weights: Weights,
    max_budget: float,
    desired_amenities: list[str] | None = None,
) -> list[HotelOption]:
    """Score, rank, and tag hotels.

    Args:
        hotels: List of raw hotel dicts from API / mock data.
        weights: User preference weights.
        max_budget: Maximum price per night.
        desired_amenities: Amenities the user wants.

    Returns:
        Top 3 HotelOption instances sorted by total_score descending,
        tagged with BEST_BALANCE, CHEAPEST, HIGHEST_RATED.
    """
    scored: list[HotelOption] = []

    for hotel in hotels:
        total, breakdown = score_hotel(
            hotel, weights, max_budget, desired_amenities,
        )
        option = HotelOption(
            id=hotel.get("id", "unknown"),
            name=hotel.get("name", "Unknown Hotel"),
            price_per_night=hotel.get("price_per_night", 0),
            rating=hotel.get("rating", 0),
            distance_km=hotel.get("distance_km", 0),
            free_cancellation=hotel.get("free_cancellation", False),
            amenities=hotel.get("amenities", []),
            total_score=total,
            score_breakdown=breakdown,
            tag=None,
        )
        scored.append(option)

    # Sort by total_score descending
    scored.sort(key=lambda o: o.total_score, reverse=True)

    # Keep top 3
    top = scored[:3]

    # Assign tags
    return _assign_tags(top)
