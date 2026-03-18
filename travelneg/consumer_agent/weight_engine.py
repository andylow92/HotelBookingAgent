"""Weight engine: converts user preference signals into scoring weights.

Takes natural-language phrases and produces a Weights object that sums to 1.0.
This is domain-agnostic — works for hotels, restaurants, events, or tours.
"""

from travelneg.shared.models import Weights

# Default balanced weights
DEFAULT_WEIGHTS = Weights(
    price=0.25,
    location=0.25,
    rating=0.20,
    flexibility=0.15,
    match=0.15,
)

# Keyword → (dimension, boost_value) mapping
_SIGNAL_MAP: dict[str, tuple[str, float]] = {
    # Price signals
    "cheap": ("price", 0.55),
    "cheapest": ("price", 0.55),
    "budget": ("price", 0.50),
    "affordable": ("price", 0.45),
    "inexpensive": ("price", 0.50),
    "low cost": ("price", 0.50),
    "under budget": ("price", 0.45),
    "save money": ("price", 0.50),
    # Location signals
    "near": ("location", 0.45),
    "close to": ("location", 0.45),
    "walking distance": ("location", 0.50),
    "location": ("location", 0.40),
    "central": ("location", 0.40),
    "nearby": ("location", 0.45),
    "best location": ("location", 0.45),
    # Rating signals
    "best rated": ("rating", 0.45),
    "highest rated": ("rating", 0.45),
    "top rated": ("rating", 0.45),
    "best reviews": ("rating", 0.45),
    "highly rated": ("rating", 0.40),
    "good reviews": ("rating", 0.35),
    "quality": ("rating", 0.35),
    # Flexibility signals
    "cancel": ("flexibility", 0.40),
    "cancellation": ("flexibility", 0.40),
    "free cancellation": ("flexibility", 0.45),
    "refund": ("flexibility", 0.40),
    "flexible": ("flexibility", 0.40),
    "might cancel": ("flexibility", 0.40),
    "flexibility": ("flexibility", 0.40),
    # Match signals
    "wifi": ("match", 0.25),
    "breakfast": ("match", 0.25),
    "pool": ("match", 0.25),
    "gym": ("match", 0.25),
    "parking": ("match", 0.25),
    "spa": ("match", 0.25),
    "amenities": ("match", 0.30),
    "features": ("match", 0.25),
}

# Signals that zero-out a dimension
_ZERO_SIGNALS: dict[str, str] = {
    "don't care about price": "price",
    "don't care about location": "location",
    "don't care about rating": "rating",
    "don't care about cancellation": "flexibility",
    "don't care about flexibility": "flexibility",
    "don't care about amenities": "match",
    "price doesn't matter": "price",
    "location doesn't matter": "location",
}


def compute_weights(preference_signals: list[str], base: Weights | None = None) -> Weights:
    """Convert a list of user preference signal phrases into scoring weights.

    Args:
        preference_signals: Natural-language phrases extracted from user message.
        base: Optional base weights to start from (for re-negotiation).

    Returns:
        Normalized Weights object summing to 1.0.
    """
    w = dict(
        price=base.price if base else DEFAULT_WEIGHTS.price,
        location=base.location if base else DEFAULT_WEIGHTS.location,
        rating=base.rating if base else DEFAULT_WEIGHTS.rating,
        flexibility=base.flexibility if base else DEFAULT_WEIGHTS.flexibility,
        match=base.match if base else DEFAULT_WEIGHTS.match,
    )

    combined = " ".join(s.lower() for s in preference_signals)

    # Check for zero-out signals first
    for phrase, dim in _ZERO_SIGNALS.items():
        if phrase in combined:
            w[dim] = 0.0

    # Apply boost signals
    boosted: dict[str, float] = {}
    for keyword, (dim, value) in _SIGNAL_MAP.items():
        if keyword in combined:
            # Keep the highest boost per dimension
            if dim not in boosted or value > boosted[dim]:
                boosted[dim] = value

    for dim, value in boosted.items():
        w[dim] = value

    weights = Weights(**w)
    return weights.normalized()
