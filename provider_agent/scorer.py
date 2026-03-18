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


# ---------------------------------------------------------------------------
# Negotiation note generation
# ---------------------------------------------------------------------------

def generate_negotiation_note(
    options: list[HotelOption],
    weights: Weights,
) -> str:
    """Build a human-readable tradeoff explanation for the top scored hotels.

    Compares BEST_BALANCE, CHEAPEST, and HIGHEST_RATED options in
    travel-advisor tone with concrete numeric values (€ prices, star
    ratings, km distances). Adapts emphasis based on the user's heaviest
    weight dimension.

    Args:
        options: Top scored/tagged HotelOption list (typically 3).
        weights: The user's preference weights.

    Returns:
        A negotiation note string, or ``""`` if no options.
    """
    # --- Guard clauses ---
    if len(options) == 0:
        return ""
    if len(options) == 1:
        o = options[0]
        return f"Only one option matched your criteria: {o.name} at €{o.price_per_night:.0f}/night."

    # --- Identify roles by tag ---
    by_tag: dict[str, HotelOption] = {o.tag: o for o in options if o.tag}
    best: HotelOption = by_tag.get("BEST_BALANCE", options[0])
    cheapest: HotelOption | None = by_tag.get("CHEAPEST")
    highest_rated: HotelOption | None = by_tag.get("HIGHEST_RATED")

    # --- Adaptive length: if scores are very close, short note ---
    scores = [o.total_score for o in options]
    if max(scores) - min(scores) < 0.05:
        return (
            f"All three options are closely matched — {best.name} edges "
            f"ahead slightly at €{best.price_per_night:.0f}/night."
        )

    # --- Detect dominant weight ---
    weight_map = {
        "price": weights.price,
        "location": weights.location,
        "rating": weights.rating,
        "cancellation": weights.cancellation,
        "amenities": weights.amenities,
    }
    dominant = max(weight_map, key=lambda k: weight_map[k])

    # --- Helper: build comparison sentence for cheapest ---
    def _cheapest_comparison() -> str:
        if cheapest is None or cheapest.id == best.id:
            return ""
        parts: list[str] = []
        price_diff = best.price_per_night - cheapest.price_per_night
        if abs(price_diff) < 1:
            parts.append("similarly priced")
        elif price_diff > 0:
            parts.append(f"€{price_diff:.0f}/night cheaper")
        else:
            parts.append(f"€{abs(price_diff):.0f}/night more")

        # Tradeoffs
        tradeoffs: list[str] = []
        rating_drop = best.rating - cheapest.rating
        if rating_drop >= 0.2:
            tradeoffs.append(f"drops to {cheapest.rating:.1f} stars")
        elif rating_drop <= -0.2:
            tradeoffs.append(f"rated higher at {cheapest.rating:.1f} stars")
        dist_diff = cheapest.distance_km - best.distance_km
        if dist_diff >= 0.2 and not (cheapest.distance_km == 0.0 and best.distance_km == 0.0):
            tradeoffs.append(f"sits {dist_diff:.1f}km further")
        elif dist_diff <= -0.2 and not (cheapest.distance_km == 0.0 and best.distance_km == 0.0):
            tradeoffs.append(f"closer at {cheapest.distance_km:.1f}km")
        if best.free_cancellation and not cheapest.free_cancellation:
            tradeoffs.append("lacks free cancellation")

        sentence = f"{cheapest.name} is {', '.join(parts)}"
        if tradeoffs:
            sentence += f" but {', '.join(tradeoffs)}"
        return sentence + "."

    # --- Helper: build comparison sentence for highest rated ---
    def _highest_rated_comparison() -> str:
        if highest_rated is None or highest_rated.id == best.id:
            return ""
        parts: list[str] = []
        parts.append(
            f"leads on rating (rated {highest_rated.rating:.1f} vs {best.rating:.1f})"
        )

        # Distance advantage
        dist_diff = best.distance_km - highest_rated.distance_km
        if abs(dist_diff) >= 0.2 and not (highest_rated.distance_km == 0.0 and best.distance_km == 0.0):
            parts.append(f"closer at {highest_rated.distance_km:.1f}km")

        # Price premium tradeoff
        price_premium = highest_rated.price_per_night - best.price_per_night
        tradeoff = ""
        if abs(price_premium) >= 1:
            tradeoff = f" but costs €{price_premium:.0f}/night more"

        sentence = f"{highest_rated.name} {', '.join(parts)}{tradeoff}"
        return sentence + "."

    # --- Lead sentence about BEST_BALANCE ---
    cancel_str = "with free cancellation" if best.free_cancellation else "without free cancellation"
    lead = (
        f"{best.name} offers the best balance at €{best.price_per_night:.0f}/night "
        f"(rated {best.rating:.1f}, {best.distance_km:.1f}km out) {cancel_str}."
    )

    # --- Compose sections ---
    cheap_section = _cheapest_comparison()
    rated_section = _highest_rated_comparison()

    # --- Reorder based on dominant weight ---
    if dominant in ("rating", "amenities") and rated_section:
        # Lead with highest-rated comparison when rating/amenities dominate
        sections = [lead, rated_section, cheap_section]
    elif dominant == "location" and rated_section:
        # Location-heavy: highest-rated often has best location, lead with it
        sections = [lead, rated_section, cheap_section]
    else:
        # Default / price / cancellation: lead with cheapest comparison
        sections = [lead, cheap_section, rated_section]

    return " ".join(s for s in sections if s)
