# Stack Research

**Domain:** Python Hotel Booking API Client with Scoring Engine  
**Researched:** 2025-01-14  
**Confidence:** HIGH (verified via PyPI)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Runtime | Modern async support, better error messages, required for Pydantic v2 performance |
| Amadeus Python SDK | 12.0.0 | Hotel API access | Official SDK with free sandbox, hotel search/book endpoints, well-documented |
| Pydantic | 2.12+ | JSON validation & models | Industry standard for Python data validation, native JSON schema support, ~10x faster than v1 |
| httpx | 0.28+ | HTTP client (backup) | Modern async-first client, needed if using raw API endpoints instead of SDK |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.13+ | Environment config | Loading API keys and settings from `.env` files |
| python-dotenv | 1.2+ | Env file loading | Loading `.env` during local development |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | 9.0+ | Test framework | Standard Python testing, excellent fixture support |
| pytest-asyncio | 1.3+ | Async test support | Required if using async httpx calls |
| respx | 0.22+ | HTTP mocking for httpx | Mock external API calls in tests without hitting real endpoints |
| ruff | 0.15+ | Linting + formatting | Replaces flake8, black, isort in one fast tool |

## Installation

```bash
# Core dependencies
pip install amadeus pydantic pydantic-settings python-dotenv

# If using httpx directly (alternative to SDK)
pip install httpx

# Dev dependencies
pip install pytest pytest-asyncio respx ruff
```

**requirements.txt:**
```
amadeus>=12.0.0
pydantic>=2.12.0
pydantic-settings>=2.13.0
python-dotenv>=1.2.0
```

**requirements-dev.txt:**
```
pytest>=9.0.0
pytest-asyncio>=1.3.0
respx>=0.22.0
ruff>=0.15.0
```

## Hotel API Decision: Amadeus Self-Service

### Why Amadeus (HIGH confidence)

| Criterion | Amadeus | Booking.com | Expedia (RAPID) | Hotels.com |
|-----------|---------|-------------|-----------------|------------|
| Free sandbox | ✅ Yes, no payment required | ❌ Partner-only | ❌ Partner-only | ❌ Partner-only |
| Hotel search | ✅ Hotel List + Hotel Offers | N/A | N/A | N/A |
| Official Python SDK | ✅ amadeus 12.0.0 | ❌ None | ❌ None | ❌ None |
| Test data quality | ✅ Realistic | N/A | N/A | N/A |
| Signup friction | 5 min (email + API key) | Weeks (partner agreement) | Weeks | Weeks |

**Amadeus Self-Service APIs:**
- `amadeus.shopping.hotel_offers_search.get()` — search hotels by city/geo
- `amadeus.shopping.hotel_offer_search.get()` — get specific hotel details
- `amadeus.booking.hotel_orders.post()` — create booking
- `amadeus.booking.hotel_orders().delete()` — cancel booking

**Sandbox limitations:**
- Test data only (not real inventory)
- 10 requests/second rate limit
- 2000 requests/month on free tier
- ✅ Sufficient for hackathon demo

**Alternative for unlimited testing:** Mock data fallback in `mock_data.py` (already planned in project).

### API Setup

1. Sign up at https://developers.amadeus.com
2. Create app → get `AMADEUS_CLIENT_ID` and `AMADEUS_CLIENT_SECRET`
3. SDK auto-handles OAuth token refresh

```python
from amadeus import Client, ResponseError

amadeus = Client(
    client_id='YOUR_API_KEY',
    client_secret='YOUR_API_SECRET',
    hostname='test'  # 'test' for sandbox, 'production' for live
)
```

## HTTP Client Decision: Amadeus SDK (not raw httpx)

### Why use the SDK over raw httpx

| Factor | Amadeus SDK | Raw httpx |
|--------|-------------|-----------|
| Auth handling | ✅ Built-in OAuth | ❌ Manual token management |
| Endpoint mapping | ✅ Pythonic methods | ❌ Build URLs manually |
| Error handling | ✅ ResponseError class | ❌ Parse errors yourself |
| Retry logic | ✅ Built-in | ❌ Implement yourself |
| Time to implement | 30 min | 2+ hours |

**Recommendation:** Use the SDK. For a 2-hour hackathon, SDK removes auth complexity.

**When to use httpx instead:**
- SDK is broken or unmaintained
- Need endpoints not in SDK
- Prefer full control over requests

## Pydantic Model Strategy

### Models Needed (from README contract)

```python
# shared/models.py
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from datetime import date

class Weights(BaseModel):
    price: float = Field(ge=0, le=1)
    location: float = Field(ge=0, le=1)
    rating: float = Field(ge=0, le=1)
    cancellation: float = Field(ge=0, le=1)
    amenities: float = Field(ge=0, le=1)
    
    @field_validator('__root__', mode='after')
    def weights_sum_to_one(cls, values):
        total = sum(values.values())
        if not (0.99 <= total <= 1.01):  # Float tolerance
            raise ValueError(f'Weights must sum to 1.0, got {total}')
        return values

class SearchRequest(BaseModel):
    action: Literal['search']
    destination: str
    check_in: date
    check_out: date
    guests: int = Field(ge=1)
    hard_constraints: dict
    weights: Weights
    context: dict = {}

class BookRequest(BaseModel):
    action: Literal['book']
    option_id: str
    guest_name: str
    check_in: date
    check_out: date

class CancelRequest(BaseModel):
    action: Literal['cancel']
    booking_id: str

class HotelOption(BaseModel):
    id: str
    name: str
    price_per_night: float
    rating: float
    distance_km: float
    free_cancellation: bool
    amenities: list[str]
    total_score: float
    score_breakdown: dict[str, float]
    tag: Literal['BEST_BALANCE', 'CHEAPEST', 'HIGHEST_RATED'] | None = None

class SearchResponse(BaseModel):
    action: Literal['search_results']
    options: list[HotelOption]
    negotiation_note: str
```

### Why Pydantic v2

- **Validation:** Automatic type checking, custom validators for weight sum
- **Serialization:** `.model_dump_json()` for Orca JSON output
- **Documentation:** Auto-generates JSON Schema for debugging
- **Performance:** v2 is compiled (Rust core), ~10x faster than v1

## Testing Strategy

### Layer 1: Unit Tests (scorer.py)

```python
# tests/test_scorer.py
def test_scoring_formula():
    """Test that score calculation matches formula"""
    result = calculate_score(
        price=89, max_budget=150,
        distance_km=0.3, max_distance=5,
        rating=4.3,
        free_cancellation=True,
        matched_amenities=2, desired_amenities=3,
        weights=Weights(price=0.25, location=0.3, rating=0.2, cancellation=0.15, amenities=0.1)
    )
    assert 0.85 < result < 0.90  # Expected ~0.87
```

### Layer 2: API Client Tests (mocked)

```python
# tests/test_api_client.py
import respx
from httpx import Response

@respx.mock
def test_hotel_search_returns_results():
    """Test API client with mocked Amadeus response"""
    respx.get("https://test.api.amadeus.com/v3/shopping/hotel-offers").mock(
        return_value=Response(200, json={...mock data...})
    )
    results = api_client.search_hotels("Berlin", "2025-03-19", "2025-03-21")
    assert len(results) > 0
```

### Layer 3: Integration Tests (with mock_data.py)

```python
# tests/test_integration.py
def test_full_search_flow_with_mock():
    """Test entire flow using mock data fallback"""
    request = SearchRequest(...)
    response = agent.handle_request(request, use_mock=True)
    assert response.action == "search_results"
    assert len(response.options) == 3
```

### Why respx over responses/pytest-httpx

| Library | Best For | Notes |
|---------|----------|-------|
| respx | httpx mocking | Native httpx support, async-aware |
| responses | requests mocking | Not compatible with httpx |
| pytest-httpx | httpx mocking (pytest plugin) | Alternative to respx, similar features |

**Recommendation:** respx — cleaner API, explicit mock setup.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Amadeus SDK | Raw httpx | If SDK has bugs or missing endpoints |
| Pydantic v2 | dataclasses + manual validation | If you need stdlib-only (unlikely) |
| respx | pytest-httpx | Personal preference, both work well |
| ruff | black + flake8 + isort | If team already uses separate tools |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Pydantic v1 | Deprecated, 10x slower, different API | Pydantic v2 (2.12+) |
| requests library | Sync-only, no HTTP/2 | httpx (modern, async-capable) |
| aiohttp | More complex, less intuitive | httpx with async |
| Booking.com / Expedia APIs | Partner-only, weeks to get access | Amadeus (free sandbox) |
| unittest.mock for HTTP | Low-level, error-prone | respx (purpose-built for httpx) |
| Manual JSON parsing | Error-prone, no validation | Pydantic models |

## Stack Patterns by Variant

**If Amadeus API is down during demo:**
- `mock_data.py` returns hardcoded realistic data
- Scorer works identically on mock data
- Demo proceeds without API dependency

**If you need async:**
```python
# Use async httpx client
async with httpx.AsyncClient() as client:
    response = await client.get(...)
```
- Add `pytest-asyncio` for async tests
- Amadeus SDK is sync-only, so wrap in `asyncio.to_thread()` if needed

**If you need to extend beyond SDK:**
```python
# Direct httpx for endpoints not in SDK
import httpx

client = httpx.Client(
    base_url="https://test.api.amadeus.com/v3",
    headers={"Authorization": f"Bearer {access_token}"}
)
```

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Pydantic 2.12+ | Python 3.8+ | Requires Python 3.8 minimum |
| httpx 0.28+ | Python 3.8+ | HTTP/2 support built-in |
| amadeus 12.0.0 | Python 3.4+ | Broadly compatible |
| pytest 9.0+ | Python 3.9+ | Dropped 3.8 support in pytest 9 |

**Recommended Python:** 3.11+ (best performance, required for pytest 9)

## Quick Start Snippet

```python
# api_client.py
from amadeus import Client, ResponseError
import os

amadeus = Client(
    client_id=os.getenv('AMADEUS_CLIENT_ID'),
    client_secret=os.getenv('AMADEUS_CLIENT_SECRET'),
    hostname='test'
)

def search_hotels(city_code: str, check_in: str, check_out: str, adults: int = 1) -> list:
    """Search hotels via Amadeus API"""
    try:
        # First get hotel IDs in the city
        hotels = amadeus.reference_data.locations.hotels.by_city.get(cityCode=city_code)
        hotel_ids = [h['hotelId'] for h in hotels.data[:10]]  # Top 10
        
        # Then get offers for those hotels
        offers = amadeus.shopping.hotel_offers_search.get(
            hotelIds=hotel_ids,
            checkInDate=check_in,
            checkOutDate=check_out,
            adults=adults
        )
        return offers.data
    except ResponseError as e:
        print(f"Amadeus error: {e}")
        return []  # Fallback to mock_data.py
```

## Sources

- PyPI (verified 2025-01-14):
  - pydantic 2.12.5 — https://pypi.org/project/pydantic/
  - httpx 0.28.1 — https://pypi.org/project/httpx/
  - amadeus 12.0.0 — https://pypi.org/project/amadeus/
  - pytest 9.0.2 — https://pypi.org/project/pytest/
  - respx 0.22.0 — https://pypi.org/project/respx/
  - ruff 0.15.6 — https://pypi.org/project/ruff/
- Amadeus Self-Service Documentation — https://developers.amadeus.com
- Amadeus Python SDK GitHub — https://github.com/amadeus4dev/amadeus-python

---
*Stack research for: Python Hotel Booking Provider Agent*  
*Researched: 2025-01-14*  
*Confidence: HIGH (all versions verified via PyPI)*
