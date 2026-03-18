# Phase 1: Data Models & Scoring Engine - Research

**Researched:** 2025-01-20
**Domain:** Pydantic Data Validation + Weighted Scoring Algorithm (Python)
**Confidence:** HIGH

## Summary

Phase 1 establishes the data foundation and business logic core for the Provider Agent. This phase creates two critical components: **Pydantic models** (shared/models.py) that validate JSON contracts between agents, and a **defensive scoring engine** (provider_agent/scorer.py) that normalizes hotel data to 0–1 scores across 5 dimensions and produces weighted total scores.

The scoring formula is the intellectual heart of the project—it transforms raw hotel data (prices, distances, ratings) into normalized 0–1 values, then applies user-defined weights to produce a single ranking score. Edge cases (€0 prices, null ratings, division by zero) MUST be handled defensively to prevent demo-breaking crashes.

**Primary recommendation:** Build models.py first (everything depends on it), then scorer.py with comprehensive edge case handling. Test scorer with intentionally malformed data before moving on.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Pydantic models in shared/models.py match README JSON schemas exactly (Consumer→Provider and Provider→Consumer) | Pydantic v2 models with field validators, exact JSON schema from README documented below |
| DATA-02 | Defensive scoring handles edge cases (€0 prices, null ratings, missing amenities, division by zero) | Defensive scoring patterns with fallback values, clamping, and explicit edge case handling |
| SRCH-02 | API response is normalized to 0–1 scores across 5 dimensions (price, location, rating, cancellation, amenities) | Normalization formulas documented with safe denominator handling |
| SRCH-03 | Scoring engine applies weighted formula — all weights sum to 1.0, produces total score 0–1 | Weight validation with auto-normalization, weighted sum formula, output clamping |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pydantic | 2.12+ | JSON validation & data models | Industry standard for Python data validation, native JSON schema support, ~10x faster than v1 |
| Python | 3.11+ | Runtime | Modern type hints, better error messages, required for Pydantic v2 performance |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | stdlib | Type annotations | Used throughout for List, Dict, Literal, Optional types |
| datetime | stdlib | Date handling | check_in/check_out fields in request models |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic v2 | dataclasses + manual validation | Pydantic is 10 lines vs 50, handles edge cases better |
| Field validators | Pre-processing in scorer | Validators catch bad data at entry point, better error messages |

**Installation:**
```bash
pip install pydantic>=2.12.0
```

## Architecture Patterns

### Recommended Project Structure
```
shared/
└── models.py          # Pydantic models for all JSON contracts

provider_agent/
└── scorer.py          # Scoring formula + ranking logic
```

### Pattern 1: Pydantic Models as Contracts
**What:** Define all JSON message formats as Pydantic BaseModels
**When to use:** Always—every JSON input/output goes through a model
**Example:**
```python
# shared/models.py
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal
from datetime import date

class Weights(BaseModel):
    """User preference weights — must sum to 1.0"""
    price: float = Field(ge=0, le=1)
    location: float = Field(ge=0, le=1)
    rating: float = Field(ge=0, le=1)
    cancellation: float = Field(ge=0, le=1)
    amenities: float = Field(ge=0, le=1)
    
    @model_validator(mode='after')
    def weights_sum_to_one(self) -> 'Weights':
        total = self.price + self.location + self.rating + self.cancellation + self.amenities
        if abs(total - 1.0) > 0.01:
            # Auto-normalize instead of rejecting
            factor = total
            object.__setattr__(self, 'price', self.price / factor)
            object.__setattr__(self, 'location', self.location / factor)
            object.__setattr__(self, 'rating', self.rating / factor)
            object.__setattr__(self, 'cancellation', self.cancellation / factor)
            object.__setattr__(self, 'amenities', self.amenities / factor)
        return self
```

### Pattern 2: Defensive Scoring with Fallbacks
**What:** Every division/calculation has a fallback for edge cases
**When to use:** Always in scorer.py—API returns garbage data in sandbox
**Example:**
```python
# provider_agent/scorer.py
def calculate_price_score(price: float, max_budget: float) -> float:
    """Price score: lower price = higher score (0–1)"""
    if max_budget <= 0:
        max_budget = 500  # Sensible default
    if price <= 0:
        return 0.5  # Unknown price = neutral score
    if price >= max_budget:
        return 0.0  # At or over budget = worst score
    return max(0.0, min(1.0, 1 - (price / max_budget)))
```

### Pattern 3: Type Coercion in Validators
**What:** Pydantic validators that convert strings to numbers
**When to use:** When receiving API data (Amadeus returns "89.00" not 89.0)
**Example:**
```python
class HotelOption(BaseModel):
    price_per_night: float
    rating: float
    
    @field_validator('price_per_night', 'rating', mode='before')
    @classmethod
    def coerce_to_float(cls, v):
        if isinstance(v, str):
            return float(v) if v else 0.0
        return v if v is not None else 0.0
```

### Anti-Patterns to Avoid
- **Direct dict access without validation:** Always parse through Pydantic first
- **Unchecked division:** Never divide without checking denominator > 0
- **Trusting API data types:** Amadeus returns strings for numbers—always coerce
- **Hardcoded magic numbers inline:** Define constants (DEFAULT_MAX_DISTANCE = 5.0)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON validation | if/else key checks | Pydantic BaseModel | Handles nested types, provides clear errors |
| Type coercion | manual str→float | Pydantic field_validator | Consistent handling, better errors |
| Weight normalization | Manual division everywhere | model_validator on Weights | Single place, auto-normalizes on input |
| Score clamping | Scattered min/max calls | Helper function clamp_score() | Consistent 0–1 output guaranteed |

**Key insight:** Pydantic v2 handles 90% of edge cases you'd otherwise code manually. Trust it.

## Common Pitfalls

### Pitfall 1: Division by Zero in Scoring
**What goes wrong:** `1 - (price / max_budget)` crashes when max_budget is 0 or None
**Why it happens:** User doesn't specify budget, or API returns garbage
**How to avoid:** 
```python
def safe_price_score(price: float, max_budget: float | None) -> float:
    budget = max_budget if max_budget and max_budget > 0 else 500
    price = price if price > 0 else budget * 0.5  # Unknown = mid-range
    return max(0.0, min(1.0, 1 - (price / budget)))
```
**Warning signs:** ZeroDivisionError, inf scores, NaN in output

### Pitfall 2: Weights Don't Sum to 1.0
**What goes wrong:** Consumer Agent sends weights summing to 0.85 or 1.15
**Why it happens:** Consumer changes one weight without redistributing
**How to avoid:** Auto-normalize in Weights model (see Pattern 1)
**Warning signs:** Scores change unexpectedly, same hotel different scores

### Pitfall 3: Null/Missing Fields Crash Scoring
**What goes wrong:** `hotel.rating / 5.0` fails when rating is None
**Why it happens:** Amadeus sandbox returns incomplete data
**How to avoid:**
```python
rating_score = (hotel.rating or 3.0) / 5.0  # Default to 3-star if missing
```
**Warning signs:** TypeError, AttributeError in scoring loop

### Pitfall 4: String vs Number Type Mismatch
**What goes wrong:** Pydantic rejects valid API data because price is "89.00" not 89.0
**Why it happens:** Amadeus returns numbers as strings
**How to avoid:** Use `mode='before'` validators to coerce types
**Warning signs:** ValidationError on API response parsing

### Pitfall 5: Amenities Score with Empty Desired List
**What goes wrong:** `matched / len(desired)` = division by zero
**Why it happens:** User doesn't specify any amenities
**How to avoid:**
```python
def amenities_score(matched: list, desired: list) -> float:
    if not desired:
        return 1.0  # No requirements = full score
    return len(set(matched) & set(desired)) / len(desired)
```
**Warning signs:** ZeroDivisionError, inf scores

## Code Examples

### Complete Weights Model with Auto-Normalization
```python
# shared/models.py
from pydantic import BaseModel, Field, model_validator

class Weights(BaseModel):
    """Scoring weights — auto-normalizes to sum to 1.0"""
    price: float = Field(ge=0, le=1, default=0.25)
    location: float = Field(ge=0, le=1, default=0.25)
    rating: float = Field(ge=0, le=1, default=0.20)
    cancellation: float = Field(ge=0, le=1, default=0.15)
    amenities: float = Field(ge=0, le=1, default=0.15)
    
    @model_validator(mode='after')
    def normalize_weights(self) -> 'Weights':
        total = self.price + self.location + self.rating + self.cancellation + self.amenities
        if total == 0:
            # All zero = equal weights
            for field in ['price', 'location', 'rating', 'cancellation', 'amenities']:
                object.__setattr__(self, field, 0.2)
        elif abs(total - 1.0) > 0.001:
            # Normalize
            object.__setattr__(self, 'price', self.price / total)
            object.__setattr__(self, 'location', self.location / total)
            object.__setattr__(self, 'rating', self.rating / total)
            object.__setattr__(self, 'cancellation', self.cancellation / total)
            object.__setattr__(self, 'amenities', self.amenities / total)
        return self
```

### Search Request Model (Consumer → Provider)
```python
# shared/models.py
from pydantic import BaseModel, Field
from typing import Literal
from datetime import date

class HardConstraints(BaseModel):
    """Non-negotiable constraints"""
    max_price_per_night: float = Field(gt=0)
    currency: str = "EUR"

class SearchContext(BaseModel):
    """Optional context for better recommendations"""
    preferred_area: str | None = None
    arrival_time: str | None = None
    desired_amenities: list[str] = []

class SearchRequest(BaseModel):
    """Consumer → Provider: search for hotels"""
    action: Literal['search']
    destination: str
    check_in: date
    check_out: date
    guests: int = Field(ge=1, default=1)
    hard_constraints: HardConstraints
    weights: Weights
    context: SearchContext = SearchContext()
```

### Hotel Option Model (Provider → Consumer)
```python
# shared/models.py
from pydantic import BaseModel, Field, field_validator
from typing import Literal

class ScoreBreakdown(BaseModel):
    """Individual dimension scores (0–1)"""
    price: float = Field(ge=0, le=1)
    location: float = Field(ge=0, le=1)
    rating: float = Field(ge=0, le=1)
    cancellation: float = Field(ge=0, le=1)
    amenities: float = Field(ge=0, le=1)

class HotelOption(BaseModel):
    """A scored hotel option returned to Consumer"""
    id: str
    name: str
    price_per_night: float
    rating: float
    distance_km: float
    free_cancellation: bool
    amenities: list[str]
    total_score: float = Field(ge=0, le=1)
    score_breakdown: ScoreBreakdown
    tag: Literal['BEST_BALANCE', 'CHEAPEST', 'HIGHEST_RATED'] | None = None
    
    @field_validator('price_per_night', 'rating', 'distance_km', mode='before')
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return 0.0
        return v if v is not None else 0.0
```

### Defensive Scoring Engine
```python
# provider_agent/scorer.py
from dataclasses import dataclass
from shared.models import Weights, ScoreBreakdown, HotelOption

# Defensive defaults
DEFAULT_MAX_BUDGET = 500.0
DEFAULT_MAX_DISTANCE = 5.0  # km
DEFAULT_RATING = 3.0  # 3-star if unknown

def clamp(value: float) -> float:
    """Ensure score is in 0–1 range"""
    return max(0.0, min(1.0, value))

def calculate_price_score(price: float, max_budget: float) -> float:
    """Lower price = higher score"""
    budget = max_budget if max_budget > 0 else DEFAULT_MAX_BUDGET
    if price <= 0:
        return 0.5  # Unknown = neutral
    if price >= budget:
        return 0.0  # At/over budget = worst
    return clamp(1 - (price / budget))

def calculate_location_score(distance_km: float, max_distance: float = DEFAULT_MAX_DISTANCE) -> float:
    """Closer = higher score"""
    if distance_km < 0:
        return 0.5  # Unknown = neutral
    if distance_km >= max_distance:
        return 0.0  # Too far = worst
    return clamp(1 - (distance_km / max_distance))

def calculate_rating_score(rating: float | None) -> float:
    """Higher rating = higher score (out of 5)"""
    r = rating if rating and rating > 0 else DEFAULT_RATING
    return clamp(r / 5.0)

def calculate_cancellation_score(free_cancellation: bool) -> float:
    """Free cancellation = 1.0, else 0.0"""
    return 1.0 if free_cancellation else 0.0

def calculate_amenities_score(hotel_amenities: list[str], desired_amenities: list[str]) -> float:
    """Fraction of desired amenities present"""
    if not desired_amenities:
        return 1.0  # No requirements = full score
    matched = len(set(hotel_amenities) & set(desired_amenities))
    return matched / len(desired_amenities)

def score_hotel(
    hotel: dict,
    weights: Weights,
    max_budget: float,
    desired_amenities: list[str] = None
) -> tuple[float, ScoreBreakdown]:
    """
    Score a single hotel with given weights.
    Returns (total_score, breakdown).
    """
    desired_amenities = desired_amenities or []
    
    # Calculate individual dimension scores
    breakdown = ScoreBreakdown(
        price=calculate_price_score(hotel.get('price_per_night', 0), max_budget),
        location=calculate_location_score(hotel.get('distance_km', 0)),
        rating=calculate_rating_score(hotel.get('rating')),
        cancellation=calculate_cancellation_score(hotel.get('free_cancellation', False)),
        amenities=calculate_amenities_score(hotel.get('amenities', []), desired_amenities)
    )
    
    # Weighted sum
    total = (
        breakdown.price * weights.price +
        breakdown.location * weights.location +
        breakdown.rating * weights.rating +
        breakdown.cancellation * weights.cancellation +
        breakdown.amenities * weights.amenities
    )
    
    return clamp(total), breakdown
```

### Book/Cancel Request Models
```python
# shared/models.py
class BookRequest(BaseModel):
    """Consumer → Provider: book a hotel"""
    action: Literal['book']
    option_id: str
    guest_name: str
    check_in: date
    check_out: date

class CancelRequest(BaseModel):
    """Consumer → Provider: cancel a booking"""
    action: Literal['cancel']
    booking_id: str

class ReadRequest(BaseModel):
    """Consumer → Provider: get booking details"""
    action: Literal['read']
    booking_id: str
```

### Search Response Model
```python
# shared/models.py
class SearchResponse(BaseModel):
    """Provider → Consumer: search results"""
    action: Literal['search_results']
    options: list[HotelOption]
    negotiation_note: str = ""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `validator` | Pydantic v2 `field_validator`, `model_validator` | Pydantic 2.0 (2023) | Different decorator names, mode parameter required |
| `@validator(..., pre=True)` | `@field_validator(..., mode='before')` | Pydantic 2.0 | Syntax change, same functionality |
| `class Config` | `model_config = ConfigDict(...)` | Pydantic 2.0 | Class-based config deprecated |

**Deprecated/outdated:**
- `@validator` decorator: Use `@field_validator` in v2
- `@root_validator`: Use `@model_validator` in v2
- `class Config`: Use `model_config = ConfigDict(...)` in v2

## Open Questions

1. **Distance calculation method**
   - What we know: README mentions "distance_km" but not how to calculate from preferred_area
   - What's unclear: Should we use Haversine formula or accept distance from API?
   - Recommendation: For Phase 1, assume distance is provided in raw hotel data. Distance calculation can be added in Phase 2 if API provides coordinates.

2. **Amenities matching strategy**
   - What we know: Score is `matched / desired`
   - What's unclear: Should matching be exact ("wifi" == "wifi") or fuzzy ("wifi" matches "free wifi")?
   - Recommendation: Start with exact match (case-insensitive). Fuzzy matching adds complexity with little demo value.

## Sources

### Primary (HIGH confidence)
- Project README.MD — exact JSON schemas, scoring formula, dimension definitions
- STACK.md — Pydantic v2.12+ recommendation, version compatibility
- PITFALLS.md — edge case handling, division by zero patterns, type coercion
- ARCHITECTURE.md — component responsibilities, build order

### Secondary (MEDIUM confidence)
- Pydantic v2 documentation patterns — validator decorators, model_validator usage
- FEATURES.md — scoring formula implementation details, default weights

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Pydantic v2 is explicitly specified in STACK.md
- Architecture: HIGH — models.py and scorer.py locations defined in ARCHITECTURE.md
- Pitfalls: HIGH — comprehensive edge cases documented in PITFALLS.md
- Scoring formula: HIGH — exact formula specified in README.MD

**Research date:** 2025-01-20
**Valid until:** 2025-02-20 (stable domain, 30 days)
