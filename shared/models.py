"""
Pydantic v2 models for all JSON contracts between Consumer and Provider agents.

Consumer → Provider: SearchRequest, BookRequest, CancelRequest, ReadRequest
Provider → Consumer: SearchResponse, HotelOption, ScoreBreakdown
Supporting: Weights, HardConstraints, SearchContext
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------

class Weights(BaseModel):
    """Scoring weights — auto-normalizes to sum to 1.0."""

    price: float = Field(ge=0, le=1, default=0.25)
    location: float = Field(ge=0, le=1, default=0.25)
    rating: float = Field(ge=0, le=1, default=0.20)
    cancellation: float = Field(ge=0, le=1, default=0.15)
    amenities: float = Field(ge=0, le=1, default=0.15)

    @model_validator(mode="after")
    def normalize_weights(self) -> Weights:
        total = (
            self.price
            + self.location
            + self.rating
            + self.cancellation
            + self.amenities
        )
        if total == 0:
            # All zero → equal weights
            for field_name in ("price", "location", "rating", "cancellation", "amenities"):
                object.__setattr__(self, field_name, 0.2)
        elif abs(total - 1.0) > 0.001:
            # Normalize so weights sum to 1.0
            object.__setattr__(self, "price", self.price / total)
            object.__setattr__(self, "location", self.location / total)
            object.__setattr__(self, "rating", self.rating / total)
            object.__setattr__(self, "cancellation", self.cancellation / total)
            object.__setattr__(self, "amenities", self.amenities / total)
        return self


class HardConstraints(BaseModel):
    """Non-negotiable constraints from the user."""

    max_price_per_night: float = Field(gt=0)
    currency: str = "EUR"


class SearchContext(BaseModel):
    """Optional context for better recommendations."""

    preferred_area: str | None = None
    arrival_time: str | None = None
    desired_amenities: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Consumer → Provider request models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    """Consumer → Provider: search for hotels."""

    action: Literal["search"]
    destination: str
    check_in: date
    check_out: date
    guests: int = Field(ge=1, default=1)
    hard_constraints: HardConstraints
    weights: Weights = Field(default_factory=Weights)
    context: SearchContext = Field(default_factory=SearchContext)


class BookRequest(BaseModel):
    """Consumer → Provider: book a hotel."""

    action: Literal["book"]
    option_id: str
    guest_name: str
    check_in: date
    check_out: date


class CancelRequest(BaseModel):
    """Consumer → Provider: cancel a booking."""

    action: Literal["cancel"]
    booking_id: str


class ReadRequest(BaseModel):
    """Consumer → Provider: get booking details."""

    action: Literal["read"]
    booking_id: str


# ---------------------------------------------------------------------------
# Provider → Consumer response models
# ---------------------------------------------------------------------------

class ScoreBreakdown(BaseModel):
    """Individual dimension scores (0–1)."""

    price: float = Field(ge=0, le=1)
    location: float = Field(ge=0, le=1)
    rating: float = Field(ge=0, le=1)
    cancellation: float = Field(ge=0, le=1)
    amenities: float = Field(ge=0, le=1)


class HotelOption(BaseModel):
    """A scored hotel option returned to Consumer."""

    id: str
    name: str
    price_per_night: float
    rating: float
    distance_km: float
    free_cancellation: bool
    amenities: list[str] = Field(default_factory=list)
    total_score: float = Field(ge=0, le=1)
    score_breakdown: ScoreBreakdown
    tag: Literal["BEST_BALANCE", "CHEAPEST", "HIGHEST_RATED"] | None = None

    @field_validator("price_per_night", "rating", "distance_km", mode="before")
    @classmethod
    def coerce_numeric(cls, v: object) -> float:
        """Coerce strings to floats — Amadeus API returns '89.00' not 89.0."""
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return 0.0
        return float(v) if v is not None else 0.0


class SearchResponse(BaseModel):
    """Provider → Consumer: search results."""

    action: Literal["search_results"]
    options: list[HotelOption] = Field(default_factory=list)
    negotiation_note: str = ""
