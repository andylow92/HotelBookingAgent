"""Domain-agnostic weighted scoring engine.

Takes a list of raw option dicts (from any travel API), a set of weights,
and domain config — returns scored and ranked ScoredOption objects.
"""

from __future__ import annotations

from travelneg.shared.domain_config import DomainConfig
from travelneg.shared.models import Coords, ScoreBreakdown, ScoredOption, Weights
from travelneg.shared.geocoding import haversine

_FLEXIBILITY_MAP = {"free": 1.0, "partial": 0.3, "none": 0.0}


def _price_score(price: float, max_budget: float) -> float:
    if max_budget <= 0:
        return 0.0
    return max(0.0, 1.0 - price / max_budget)


def _location_score(
    distance_km: float | None,
    max_distance_km: float,
) -> float:
    if distance_km is None or max_distance_km <= 0:
        return 0.5  # neutral when unknown
    return max(0.0, 1.0 - distance_km / max_distance_km)


def _rating_score(rating: float, max_rating: float = 5.0) -> float:
    if max_rating <= 0:
        return 0.0
    return min(rating / max_rating, 1.0)


def _flexibility_score(flexibility: str) -> float:
    return _FLEXIBILITY_MAP.get(flexibility.lower().strip(), 0.0)


def _match_score(matched: list[str], desired: list[str]) -> float:
    if not desired:
        return 1.0  # nothing desired means everything matches
    count = sum(1 for f in desired if f.lower() in [m.lower() for m in matched])
    return count / len(desired)


def compute_distance(
    option_coords: Coords | None,
    preferred_coords: Coords | None,
) -> float | None:
    """Return distance in km, or None if either coord is missing."""
    if option_coords is None or preferred_coords is None:
        return None
    return round(haversine(preferred_coords, option_coords), 2)


def score_option(
    *,
    option_id: str,
    name: str,
    price: float,
    rating: float,
    distance_km: float | None,
    flexibility: str,
    matched_features: list[str],
    desired_features: list[str],
    weights: Weights,
    max_budget: float,
    domain: DomainConfig,
    raw: dict | None = None,
) -> ScoredOption:
    """Score a single option and return a ScoredOption."""
    w = weights.normalized()

    ps = _price_score(price, max_budget)
    ls = _location_score(distance_km, domain.max_distance_km)
    rs = _rating_score(rating)
    fs = _flexibility_score(flexibility)
    ms = _match_score(matched_features, desired_features)

    total = (
        ps * w.price
        + ls * w.location
        + rs * w.rating
        + fs * w.flexibility
        + ms * w.match
    )

    return ScoredOption(
        id=option_id,
        name=name,
        price=price,
        rating=rating,
        distance_km=distance_km,
        flexibility=flexibility,
        matched_features=matched_features,
        total_score=round(total, 4),
        score_breakdown=ScoreBreakdown(
            price=round(ps, 4),
            location=round(ls, 4),
            rating=round(rs, 4),
            flexibility=round(fs, 4),
            match=round(ms, 4),
        ),
        raw=raw or {},
    )


def rank_and_tag(options: list[ScoredOption], top_n: int = 3) -> list[ScoredOption]:
    """Sort by total_score descending, tag the top options, and return top_n."""
    options.sort(key=lambda o: o.total_score, reverse=True)

    # Tag special options
    if options:
        cheapest = min(options, key=lambda o: o.price)
        cheapest.tag = "CHEAPEST"
        highest_rated = max(options, key=lambda o: o.rating)
        highest_rated.tag = "HIGHEST_RATED"
        options[0].tag = options[0].tag or "BEST_BALANCE"

    return options[:top_n]


def generate_negotiation_note(ranked: list[ScoredOption], max_budget: float) -> str:
    """Generate a concise negotiation note explaining tradeoffs."""
    if not ranked:
        return "No options found matching your criteria."

    parts: list[str] = []
    top = ranked[0]
    savings_pct = round((1 - top.price / max_budget) * 100) if max_budget > 0 else 0

    parts.append(
        f"Top pick: {top.name} at {top.price} "
        f"({savings_pct}% under budget, score {top.total_score})"
    )

    if top.distance_km is not None:
        parts.append(f"{top.distance_km}km away")

    for opt in ranked[1:]:
        diff = []
        if opt.price < top.price:
            diff.append(f"cheaper ({opt.price})")
        if opt.rating > top.rating:
            diff.append(f"higher rated ({opt.rating})")
        if opt.distance_km is not None and top.distance_km is not None:
            if opt.distance_km < top.distance_km:
                diff.append(f"closer ({opt.distance_km}km)")
        tradeoff = ", ".join(diff) if diff else "similar profile"
        parts.append(f"{opt.name}: {tradeoff} but lower overall score ({opt.total_score})")

    return ". ".join(parts) + "."
