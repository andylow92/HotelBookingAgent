"""Domain-specific configuration for each possible hackathon assignment."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainConfig:
    """Holds the labels and defaults that change per travel domain."""

    name: str
    # Human-readable labels for the 5 scoring dimensions
    price_label: str
    location_label: str
    rating_label: str
    flexibility_label: str
    match_label: str
    # Default max values used for normalisation
    max_distance_km: float = 5.0
    max_budget_default: float = 200.0
    # Feature keywords the match dimension can compare against
    common_features: tuple[str, ...] = ()


DOMAINS: dict[str, DomainConfig] = {
    "hotels": DomainConfig(
        name="hotels",
        price_label="price per night",
        location_label="distance to preferred area",
        rating_label="guest rating",
        flexibility_label="cancellation policy",
        match_label="amenities",
        max_distance_km=5.0,
        max_budget_default=200.0,
        common_features=("wifi", "breakfast", "pool", "gym", "parking", "spa"),
    ),
    "restaurants": DomainConfig(
        name="restaurants",
        price_label="price per person",
        location_label="distance to user",
        rating_label="guest rating",
        flexibility_label="reservation flexibility",
        match_label="cuisine / dietary",
        max_distance_km=3.0,
        max_budget_default=60.0,
        common_features=("vegan", "gluten-free", "outdoor", "halal", "terrace"),
    ),
    "events": DomainConfig(
        name="events",
        price_label="ticket price",
        location_label="distance to user",
        rating_label="event rating",
        flexibility_label="refund policy",
        match_label="category / interest",
        max_distance_km=10.0,
        max_budget_default=100.0,
        common_features=("music", "art", "tech", "food", "outdoor", "family"),
    ),
    "tours": DomainConfig(
        name="tours",
        price_label="tour price",
        location_label="distance to meeting point",
        rating_label="tour rating",
        flexibility_label="cancellation policy",
        match_label="language / group size",
        max_distance_km=10.0,
        max_budget_default=150.0,
        common_features=("english", "spanish", "small-group", "private", "accessible"),
    ),
}


def get_domain(name: str) -> DomainConfig:
    key = name.lower().strip()
    if key not in DOMAINS:
        raise ValueError(f"Unknown domain '{name}'. Choose from: {list(DOMAINS)}")
    return DOMAINS[key]
