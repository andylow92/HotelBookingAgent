# Architecture Research

**Domain:** Hotel Booking Provider Agent (API Integration + Scoring Engine)
**Researched:** 2025-01-18
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL BOUNDARY                               │
│                                                                          │
│    [Consumer Agent]  ──(JSON)──→  [Orca]  ──(JSON)──→  [Provider Agent] │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PROVIDER AGENT (You own this)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                         agent.py (Router)                         │   │
│  │  • Receives JSON request                                          │   │
│  │  • Routes action to handler: search → Scorer, book/cancel → API   │   │
│  │  • Formats response JSON                                          │   │
│  └───────────┬──────────────────────────────────┬───────────────────┘   │
│              │                                  │                        │
│              ▼                                  ▼                        │
│  ┌─────────────────────────┐       ┌─────────────────────────┐          │
│  │      scorer.py          │       │     api_client.py       │          │
│  │  • Score calculation    │       │  • API HTTP calls       │          │
│  │  • Ranking algorithm    │       │  • Response parsing     │          │
│  │  • Tagging (BEST,       │       │  • Error handling       │          │
│  │    CHEAPEST, TOP_RATED) │       │  • Rate limiting        │          │
│  │  • Negotiation note     │       └───────────┬─────────────┘          │
│  └─────────────────────────┘                   │                        │
│              │                                  │                        │
│              │                                  ▼                        │
│              │                      ┌─────────────────────────┐          │
│              │                      │     mock_data.py        │          │
│              │                      │  • Fallback when API    │          │
│              │                      │    is down/slow         │          │
│              │                      │  • Realistic test data  │          │
│              │                      └─────────────────────────┘          │
│              │                                  │                        │
│              └───────────┬──────────────────────┘                        │
│                          ▼                                               │
│              ┌─────────────────────────────────────────────────────────┐ │
│              │                  shared/models.py                        ││
│              │  • Pydantic models for request/response                  ││
│              │  • Validation of JSON schema                             ││
│              │  • Type safety across components                         ││
│              └─────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │       Hotel API (Amadeus)      │
                    │  • /shopping/hotel-offers      │
                    │  • /booking/hotel-bookings     │
                    └───────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Owns | Does NOT Own |
|-----------|----------------|------|--------------|
| **agent.py** | Request routing, response formatting | Action dispatch, JSON shape | Scoring logic, API calls |
| **api_client.py** | External API communication | HTTP calls, auth, retries | Scoring, business logic |
| **scorer.py** | Business intelligence | Score formula, ranking, tags, negotiation notes | Data fetching, routing |
| **mock_data.py** | Fallback data source | Realistic test data | Live API calls |
| **shared/models.py** | Data contracts | Pydantic schemas, validation | Business logic |

## Recommended Project Structure

```
provider_agent/
├── agent.py           # Entry point: routes actions, formats responses
├── api_client.py      # Hotel API wrapper (Amadeus/similar)
├── scorer.py          # Scoring formula + ranking + negotiation notes
└── mock_data.py       # Fallback data when API is down

shared/
├── models.py          # Pydantic models matching JSON contract
└── orca_config.py     # Orca SDK setup (Person C adds later)
```

### Structure Rationale

- **provider_agent/agent.py:** Single entry point. Consumer Agent only talks to `agent.py`. This is the facade that hides internal complexity.
- **provider_agent/api_client.py:** Isolated API concerns. If you switch from Amadeus to Booking.com API, only this file changes.
- **provider_agent/scorer.py:** Isolated business logic. Scoring formula changes don't touch API code.
- **provider_agent/mock_data.py:** Fallback without changing any other code — just swap the data source.
- **shared/models.py:** Single source of truth for JSON schemas. Both agents import from here.

## Architectural Patterns

### Pattern 1: Facade Pattern (agent.py)

**What:** Single entry point that routes requests to appropriate handlers
**When to use:** When external callers shouldn't know internal structure
**Trade-offs:** Simple interface (+), extra layer (neutral for this size)

**Example:**
```python
# agent.py — the only entry point
def handle_request(request: ProviderRequest) -> ProviderResponse:
    """Route action to appropriate handler."""
    if request.action == "search":
        return _handle_search(request)
    elif request.action == "book":
        return _handle_book(request)
    elif request.action == "read":
        return _handle_read(request)
    elif request.action == "cancel":
        return _handle_cancel(request)
    else:
        raise ValueError(f"Unknown action: {request.action}")

def _handle_search(request: SearchRequest) -> SearchResponse:
    # 1. Fetch hotels (API or mock)
    raw_hotels = api_client.search_hotels(
        destination=request.destination,
        check_in=request.check_in,
        check_out=request.check_out,
        max_price=request.hard_constraints.max_price_per_night
    )
    # 2. Score and rank
    scored = scorer.score_and_rank(raw_hotels, request.weights, request.context)
    # 3. Format response
    return SearchResponse(
        action="search_results",
        options=scored.top_3,
        negotiation_note=scored.negotiation_note
    )
```

### Pattern 2: Adapter Pattern (api_client.py)

**What:** Wrap external API to match internal data models
**When to use:** External API response format differs from your internal needs
**Trade-offs:** Decouples external changes (+), translation overhead (negligible)

**Example:**
```python
# api_client.py — adapts Amadeus responses to internal Hotel model
class HotelAPIClient:
    def __init__(self, use_mock: bool = False):
        self._use_mock = use_mock
        self._amadeus = None
        if not use_mock:
            self._amadeus = amadeus.Client(
                client_id=os.getenv("AMADEUS_API_KEY"),
                client_secret=os.getenv("AMADEUS_API_SECRET"),
                hostname="test"  # sandbox
            )

    def search_hotels(
        self, destination: str, check_in: str, check_out: str, max_price: float
    ) -> list[Hotel]:
        if self._use_mock:
            return mock_data.get_mock_hotels(destination)
        
        try:
            response = self._amadeus.shopping.hotel_offers.get(
                cityCode=self._get_city_code(destination),
                checkInDate=check_in,
                checkOutDate=check_out,
                priceRange=f"0-{int(max_price)}"
            )
            return [self._adapt_hotel(h) for h in response.data]
        except amadeus.ResponseError as e:
            # Fallback to mock on API error
            return mock_data.get_mock_hotels(destination)

    def _adapt_hotel(self, amadeus_hotel: dict) -> Hotel:
        """Convert Amadeus response to internal Hotel model."""
        return Hotel(
            id=amadeus_hotel["hotel"]["hotelId"],
            name=amadeus_hotel["hotel"]["name"],
            price_per_night=float(amadeus_hotel["offers"][0]["price"]["total"]),
            rating=amadeus_hotel["hotel"].get("rating", 0) / 10 * 5,  # Convert to 0-5
            distance_km=self._parse_distance(amadeus_hotel),
            free_cancellation=self._has_free_cancellation(amadeus_hotel),
            amenities=self._parse_amenities(amadeus_hotel)
        )
```

### Pattern 3: Strategy Pattern (scorer.py)

**What:** Scoring formula that can be configured with different weights
**When to use:** When calculation logic stays same but parameters change
**Trade-offs:** Flexible scoring (+), weights must be validated

**Example:**
```python
# scorer.py — weighted scoring strategy
@dataclass
class ScoringWeights:
    price: float
    location: float
    rating: float
    cancellation: float
    amenities: float
    
    def __post_init__(self):
        total = self.price + self.location + self.rating + self.cancellation + self.amenities
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

def score_hotel(hotel: Hotel, weights: ScoringWeights, context: SearchContext) -> ScoredHotel:
    """Apply weighted formula to a single hotel."""
    breakdown = ScoreBreakdown(
        price=1 - (hotel.price_per_night / context.max_price),
        location=1 - (hotel.distance_km / context.max_distance),
        rating=hotel.rating / 5.0,
        cancellation=1.0 if hotel.free_cancellation else (0.3 if hotel.paid_cancellation else 0.0),
        amenities=len(set(hotel.amenities) & set(context.desired_amenities)) / max(len(context.desired_amenities), 1)
    )
    
    total_score = (
        breakdown.price * weights.price +
        breakdown.location * weights.location +
        breakdown.rating * weights.rating +
        breakdown.cancellation * weights.cancellation +
        breakdown.amenities * weights.amenities
    )
    
    return ScoredHotel(hotel=hotel, score=total_score, breakdown=breakdown)
```

### Pattern 4: Fail-Safe Fallback (mock_data.py)

**What:** Pre-defined fallback data when external service fails
**When to use:** Demo/hackathon scenarios, unreliable external APIs
**Trade-offs:** Demo reliability (+), data may not match real API exactly

**Example:**
```python
# mock_data.py — realistic fallback data
BERLIN_HOTELS = [
    Hotel(
        id="mock_1",
        name="Motel One Berlin-Alexanderplatz",
        price_per_night=89,
        rating=4.3,
        distance_km=0.3,
        free_cancellation=True,
        amenities=["wifi", "breakfast"]
    ),
    Hotel(
        id="mock_2",
        name="Generator Berlin Mitte",
        price_per_night=62,
        rating=3.6,
        distance_km=1.2,
        free_cancellation=False,
        amenities=["wifi"]
    ),
    # ... more hotels
]

def get_mock_hotels(destination: str) -> list[Hotel]:
    """Return realistic mock data for destination."""
    # Map destinations to mock data sets
    mock_db = {
        "berlin": BERLIN_HOTELS,
        "paris": PARIS_HOTELS,
        "london": LONDON_HOTELS,
    }
    normalized = destination.lower().strip()
    return mock_db.get(normalized, BERLIN_HOTELS)  # Default to Berlin
```

## Data Flow

### Search Flow (Primary)

```
Consumer Agent
    │
    ▼ (JSON: action="search", destination, dates, weights)
agent.py
    │
    ├── Validate request against Pydantic model
    │
    ▼
api_client.search_hotels()
    │
    ├── Try Amadeus API
    │   └── On failure → fallback to mock_data
    │
    ▼ (list[Hotel])
scorer.score_and_rank()
    │
    ├── Score each hotel with weighted formula
    ├── Sort by total_score descending
    ├── Tag top 3: BEST_BALANCE, CHEAPEST, HIGHEST_RATED
    ├── Generate negotiation_note
    │
    ▼ (ScoredResults)
agent.py
    │
    ├── Format as ProviderResponse
    │
    ▼ (JSON: action="search_results", options[], negotiation_note)
Consumer Agent
```

### Re-scoring Flow (No API Call)

```
Consumer Agent
    │
    ▼ (JSON: action="search", same constraints, DIFFERENT weights)
agent.py
    │
    ├── Check if we have cached hotels for this search
    │   └── YES → skip API call, go straight to scorer
    │
    ▼
scorer.score_and_rank()
    │
    ├── Re-score with new weights
    ├── Re-rank (order changes!)
    ├── Re-tag
    ├── New negotiation_note
    │
    ▼
Consumer Agent
```

**Key insight:** Re-scoring doesn't need a new API call. Cache raw hotels from first search, re-score instantly when weights change. This is the "negotiation" magic.

### Book/Read/Cancel Flows

```
Consumer Agent
    │
    ▼ (JSON: action="book", option_id, guest_name)
agent.py
    │
    ├── Route to _handle_book()
    │
    ▼
api_client.book_hotel()
    │
    ├── Call Amadeus booking endpoint
    │   └── On failure → return error (no mock for real bookings)
    │
    ▼ (BookingConfirmation)
agent.py
    │
    ├── Format response
    │
    ▼ (JSON: action="booking_confirmed", booking_id, ...)
Consumer Agent
```

### Error Handling Boundaries

| Component | Handles | Propagates Up |
|-----------|---------|---------------|
| **api_client.py** | Network errors, API auth, rate limits | Returns empty list OR raises `APIError` |
| **scorer.py** | Invalid weights, empty hotel list | Raises `ScoringError` |
| **agent.py** | Unknown actions, validation failures | Returns error response JSON |

**Principle:** Each component catches what it can handle, propagates what it can't.

```python
# agent.py — error boundary at the top
def handle_request(request_json: dict) -> dict:
    try:
        request = ProviderRequest.model_validate(request_json)
        response = _dispatch(request)
        return response.model_dump()
    except ValidationError as e:
        return {"error": "invalid_request", "details": str(e)}
    except APIError as e:
        return {"error": "api_error", "details": str(e)}
    except ScoringError as e:
        return {"error": "scoring_error", "details": str(e)}
    except Exception as e:
        return {"error": "internal_error", "details": str(e)}
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Hackathon demo | Current design is perfect. Single-threaded, in-memory cache. |
| 100 concurrent users | Add caching layer (Redis) for hotel search results |
| 1000+ users | Rate limit API calls, queue requests, consider async |

### Not Relevant For Hackathon

Don't optimize for scale. The architecture above handles the demo perfectly. Focus on:
1. Reliability (mock fallback works)
2. Correctness (scoring formula is right)
3. Speed (no unnecessary API calls on re-score)

## Anti-Patterns

### Anti-Pattern 1: Scorer Calls API

**What people do:** Put API calls inside scorer.py
**Why it's wrong:** Mixes concerns, can't re-score without re-fetching
**Do this instead:** Scorer receives data, never fetches it

### Anti-Pattern 2: Business Logic in agent.py

**What people do:** Put scoring formula in agent.py
**Why it's wrong:** Makes routing code bloated, hard to test scoring
**Do this instead:** agent.py only routes and formats, scorer.py owns the formula

### Anti-Pattern 3: No Validation Layer

**What people do:** Trust incoming JSON, access keys directly
**Why it's wrong:** Crashes on missing fields, hard to debug
**Do this instead:** Pydantic models validate and provide clear errors

### Anti-Pattern 4: Inline Mock Data

**What people do:** Put mock data inside api_client.py with if/else
**Why it's wrong:** Clutters API code, hard to maintain
**Do this instead:** Separate mock_data.py, swap at client init time

### Anti-Pattern 5: Re-fetching on Weight Change

**What people do:** Call API again when user changes weights
**Why it's wrong:** Slow, wastes API calls, bad UX
**Do this instead:** Cache raw results, re-score instantly

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Amadeus API | REST via SDK | Sandbox = free, needs API key, rate limited |
| Orca (Lexia) | JSON messages | Person C wraps your functions |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| agent.py ↔ api_client.py | Function calls | Pass `Hotel` objects, not raw dicts |
| agent.py ↔ scorer.py | Function calls | Pass hotels + weights, get scored results |
| All ↔ models.py | Import models | Pydantic enforces schema everywhere |
| agent.py ↔ Orca | JSON dicts | Orca passes raw JSON, you validate with Pydantic |

## Build Order (Dependencies)

Components must be built in this order due to dependencies:

```
Phase 1: Foundation
├── shared/models.py    # Everything depends on this
│
Phase 2: Data Sources (parallel)
├── mock_data.py        # No dependencies except models
├── api_client.py       # Depends on models, mock_data for fallback
│
Phase 3: Business Logic
├── scorer.py           # Depends on models (Hotel, Weights, ScoredHotel)
│
Phase 4: Integration
├── agent.py            # Depends on all above
```

### Build Order Rationale

1. **models.py first** — Every other file imports from here. Define `Hotel`, `ScoredHotel`, `ProviderRequest`, `ProviderResponse` schemas before writing any logic.

2. **mock_data.py and api_client.py parallel** — Neither depends on the other. Mock data needs `Hotel` model. API client needs `Hotel` model and uses mock_data as fallback (but fallback can be wired later).

3. **scorer.py after models** — Needs `Hotel`, `Weights`, `ScoredHotel` types. Can be tested independently with mock hotels.

4. **agent.py last** — The glue that connects everything. Can only be completed after all components exist.

### Testing Strategy Per Phase

| Phase | Can Test Independently? | How |
|-------|------------------------|-----|
| models.py | Yes | Validate sample JSON |
| mock_data.py | Yes | Call function, check output |
| api_client.py | Yes | Mock API responses OR use sandbox |
| scorer.py | Yes | Pass mock hotels + weights, verify scores |
| agent.py | Yes | Pass JSON, verify response JSON |

## Sources

- Project requirements: README.MD, PROJECT.md
- Amadeus API documentation (well-known pattern for hotel search APIs)
- Standard patterns: Facade, Adapter, Strategy, Fail-Safe Fallback
- Hackathon architecture best practices: minimize complexity, maximize reliability

---
*Architecture research for: Hotel Booking Provider Agent*
*Researched: 2025-01-18*
