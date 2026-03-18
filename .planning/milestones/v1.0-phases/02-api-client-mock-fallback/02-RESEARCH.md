# Phase 2: API Client & Mock Fallback - Research

**Researched:** 2026-03-18
**Domain:** Amadeus Python SDK hotel search + mock data fallback
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Fail once, fall back immediately — no retries on any error
- 5-second request timeout before treating as failure
- Missing API credentials (no key/secret set) → skip API call entirely, go straight to mock data
- All error types trigger fallback: 4xx, 5xx, timeouts, connection errors
- No distinction between "API is down" vs "bad request" — for a demo, always prefer returning results over surfacing errors

### Claude's Discretion
- Mock data realism — how many hotels, static vs randomized, level of detail
- API credential handling — env vars, config file, or other approach
- Whether the caller is informed it received mock data (silent vs flagged fallback)
- Amadeus API endpoint selection and query parameter mapping
- Response parsing and normalization to match Phase 1 data models

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SRCH-01 | Provider Agent calls Amadeus API with destination, dates, guests, and max price constraints | Amadeus SDK two-step flow: Hotel List by city → Hotel Offers Search by hotel IDs. SDK handles auth, token refresh. See Architecture Patterns and Code Examples. |
| RLBL-01 | Mock data fallback (mock_data.py) returns realistic Berlin hotel results when API is unavailable | Static mock data matching the normalized dict format expected by `scorer.score_and_rank()`. 6-8 Berlin hotels with varied prices, ratings, distances, amenities. See Mock Data Pattern. |
| RLBL-02 | Graceful error handling auto-falls back to mock data on API failure | Broad `try/except` catching `ResponseError` and `Exception`. No retries per locked decisions. `is_mock` flag on return value. See Fallback Pattern. |
</phase_requirements>

<research_summary>
## Summary

Researched the Amadeus Python SDK for hotel search and the fallback architecture needed for a hackathon demo. The Amadeus Hotel Search API is a **two-step process**: first call Hotel List by City (`/v1/reference-data/locations/hotels/by-city`) to get hotel IDs, then call Hotel Offers Search (`/v3/shopping/hotel-offers`) with those IDs to get prices and availability. The SDK handles OAuth2 token management automatically.

The key challenge is **response normalization**: Amadeus returns deeply nested JSON with hotel data in `offer.hotel` and pricing in `offer.offers[0].price`. This must be flattened into the dict format expected by `scorer.score_and_rank()` — keys like `id`, `name`, `price_per_night`, `rating`, `distance_km`, `free_cancellation`, `amenities`. The Amadeus sandbox does NOT return `distance_km` or `amenities` in a structured way, so these need sensible defaults or mock enrichment.

The fallback pattern is straightforward: a single `search_hotels()` function that tries the API, catches any exception, and falls back to mock data. Per locked decisions, there are no retries and missing credentials skip the API entirely. The return value should include an `is_mock` boolean flag so downstream consumers (Phase 3+) can optionally surface this.

**Primary recommendation:** Use `amadeus` SDK with env vars `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET`. Two-step API call with 5s timeout. Static mock data for 6-8 Berlin hotels. Return `(hotels: list[dict], is_mock: bool)` tuple from `search_hotels()`.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| amadeus | 9.2.0+ | Amadeus API SDK — hotel search, booking | Official SDK, handles OAuth2 token lifecycle, maps all API paths to Python methods |
| pydantic | 2.12+ | Data validation (already installed) | Phase 1 models — used for response validation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| os (stdlib) | — | Environment variable access | Reading `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| amadeus SDK | raw `requests` + OAuth2 | SDK handles token refresh, error typing, path mapping — raw HTTP adds 50+ lines of boilerplate |
| env vars | .env file + python-dotenv | env vars are simpler, no extra dependency; .env would need gitignore management |

**Installation:**
```bash
pip install amadeus
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```
provider_agent/
├── api_client.py      # search_hotels() — API call + fallback orchestration
├── mock_data.py       # get_mock_hotels() — static Berlin hotel data
├── scorer.py          # (Phase 1 — already exists)
└── __init__.py
```

### Pattern 1: Two-Step Amadeus Hotel Search
**What:** Hotel search requires two API calls: first get hotel IDs by city, then get offers for those hotels.
**When to use:** Every hotel search request.
**Why:** Amadeus Hotel Offers Search (v3) requires `hotelIds` — you cannot search by city name directly in the offers endpoint.

```python
# Step 1: Get hotel IDs for the city
hotel_list = amadeus.reference_data.locations.hotels.by_city.get(
    cityCode='BER'
)
hotel_ids = [h['hotelId'] for h in hotel_list.data[:20]]  # Limit to 20

# Step 2: Get offers for those hotels
offers = amadeus.shopping.hotel_offers_search.get(
    hotelIds=','.join(hotel_ids),
    adults='1',
    checkInDate='2026-03-19',
    checkOutDate='2026-03-21'
)
# offers.data is a list of hotel offer objects
```

### Pattern 2: Immediate Fallback (No Retry)
**What:** Single try/except wrapping the entire API call chain. Any failure → mock data.
**When to use:** Per locked decision — all errors trigger fallback.

```python
def search_hotels(destination, check_in, check_out, guests, max_price):
    """Returns (list[dict], is_mock: bool)."""
    client = _get_client()
    if client is None:
        # No credentials → straight to mock
        return get_mock_hotels(), True

    try:
        raw = _call_amadeus(client, destination, check_in, check_out, guests, max_price)
        hotels = _normalize_response(raw)
        return hotels, False
    except Exception:
        return get_mock_hotels(), True
```

### Pattern 3: Response Normalization
**What:** Transform nested Amadeus response into flat dicts matching `scorer.score_hotel()` input.
**When to use:** After every successful API call.

The Amadeus Hotel Offers Search v3 response structure (per hotel):
```json
{
  "type": "hotel-offers",
  "hotel": {
    "hotelId": "RTBERXYZ",
    "name": "Motel One Berlin-Alexanderplatz",
    "cityCode": "BER",
    "latitude": 52.5219,
    "longitude": 13.4132
  },
  "offers": [
    {
      "id": "offer123",
      "price": {
        "currency": "EUR",
        "total": "178.00"
      },
      "policies": {
        "cancellations": [
          { "type": "FULL_REFUND", "deadline": "..." }
        ]
      },
      "room": {
        "description": { "text": "Standard Room" }
      }
    }
  ]
}
```

Normalize to:
```python
{
    "id": hotel["hotel"]["hotelId"],
    "name": hotel["hotel"]["name"],
    "price_per_night": float(offer["price"]["total"]) / num_nights,
    "rating": hotel["hotel"].get("rating", None),  # Often missing in sandbox
    "distance_km": 0.0,  # Not provided by API — use default
    "free_cancellation": _has_free_cancellation(offer),
    "amenities": [],  # Not in offers response — use empty
}
```

### Anti-Patterns to Avoid
- **Calling Hotel Offers Search without Hotel List first:** The offers endpoint requires `hotelIds` — it will fail with a 400 if you pass a city name.
- **Passing too many hotel IDs at once:** Amadeus limits to ~50 hotel IDs per request. Batch with first 20 to stay safe and fast.
- **Retrying on failure:** Per locked decisions, no retries — fail once, fall back immediately.
- **Raising exceptions from the API layer:** The caller (Phase 3) should never see API errors. Always return data.
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth2 token management | Custom token refresh logic | `amadeus.Client` | SDK auto-refreshes expired tokens, handles test/prod environments |
| HTTP request + retry | `requests.get()` with custom headers | `amadeus` SDK methods | SDK builds correct URLs, headers, query params automatically |
| City code lookup | Mapping city names to IATA codes | Hardcode `BER` for Berlin demo | Only one city needed for hackathon; a lookup adds complexity with no demo value |
| Response pagination | Custom page iteration | Limit hotel IDs to 20 | Demo shows top 3; fetching pages wastes API quota |

**Key insight:** The Amadeus SDK is a thin wrapper over HTTP but handles OAuth2 token lifecycle — the one thing that's genuinely painful to do manually. For everything else (normalization, fallback), custom code is simpler than any abstraction.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Amadeus Sandbox Returns Limited/Fake Data
**What goes wrong:** Sandbox responses have missing fields, unrealistic prices, or empty results for some cities.
**Why it happens:** The test environment uses synthetic data, not real hotel inventory. Berlin (`BER`) has reasonable coverage but fields like `rating` and room amenities are often absent.
**How to avoid:** Defensive parsing with `.get()` and fallback defaults for every field. Treat missing `rating` as `None` (scorer already handles this with `DEFAULT_RATING=3.0`). Don't depend on `distance_km` from API — it's not in the offers response.
**Warning signs:** `hotel.get("rating")` returns `None` frequently; `offers` list is empty for some hotels.

### Pitfall 2: City Code vs City Name Confusion
**What goes wrong:** Passing "Berlin" to the Hotel List API instead of "BER" (IATA code).
**Why it happens:** The `by_city` endpoint requires IATA city codes, not city names.
**How to avoid:** Hardcode the mapping for the demo: `{"Berlin": "BER"}`. For production, use the `reference_data.locations.cities` endpoint to resolve names.
**Warning signs:** 400 errors or empty results from Hotel List endpoint.

### Pitfall 3: Price Is Total Stay, Not Per Night
**What goes wrong:** Displaying €178 as "per night" when it's actually the total for 2 nights (€89/night).
**Why it happens:** Amadeus `offer.price.total` is the full stay cost. Need to divide by number of nights.
**How to avoid:** Calculate `num_nights = (check_out - check_in).days` and divide the total price.
**Warning signs:** Hotel prices in results seem much higher than expected.

### Pitfall 4: SDK Timeout Not Configurable via Parameter
**What goes wrong:** API calls hang for 30+ seconds on network issues, blocking the demo.
**Why it happens:** The Amadeus Python SDK uses `urllib` internally and doesn't expose a request-level timeout parameter in the `Client` constructor.
**How to avoid:** Set `http_timeout` if available in newer SDK versions, or wrap the API call in a `signal.alarm(5)` / `threading.Timer` pattern for a 5-second hard timeout. Test the SDK version's timeout behavior before relying on it.
**Warning signs:** Demo freezes when API is slow.

### Pitfall 5: Rate Limiting (429) on Sandbox
**What goes wrong:** After repeated calls, the sandbox returns 429 Too Many Requests.
**Why it happens:** Free tier has rate limits (typically 10 requests/second, 1000/month on test).
**How to avoid:** Per locked decisions, 429 triggers fallback to mock data. No retry needed. The fallback makes this a non-issue for the demo.
**Warning signs:** `ResponseError` with status code 429.
</common_pitfalls>

<code_examples>
## Code Examples

### Amadeus Client Initialization with Credential Check
```python
# Source: amadeus PyPI docs + project decision (env vars)
import os
from amadeus import Client, ResponseError

def _get_client() -> Client | None:
    """Return Amadeus client or None if credentials missing."""
    client_id = os.environ.get("AMADEUS_CLIENT_ID")
    client_secret = os.environ.get("AMADEUS_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None  # No credentials → caller should use mock data
    return Client(
        client_id=client_id,
        client_secret=client_secret,
        # hostname='test' is the default — sandbox environment
    )
```

### Two-Step Hotel Search
```python
# Source: amadeus-code-examples + SDK source
CITY_CODES = {"Berlin": "BER", "berlin": "BER"}

def _call_amadeus(client, destination, check_in, check_out, guests, max_price):
    """Execute the two-step hotel search. Raises on any error."""
    city_code = CITY_CODES.get(destination, destination.upper()[:3])

    # Step 1: Get hotel IDs
    hotel_list = client.reference_data.locations.hotels.by_city.get(
        cityCode=city_code
    )
    hotel_ids = [h["hotelId"] for h in hotel_list.data[:20]]
    if not hotel_ids:
        raise ValueError("No hotels found for city")

    # Step 2: Get offers
    response = client.shopping.hotel_offers_search.get(
        hotelIds=",".join(hotel_ids),
        adults=str(guests),
        checkInDate=str(check_in),
        checkOutDate=str(check_out),
        priceRange=f"0-{int(max_price)}",
        currency="EUR",
    )
    return response.data
```

### Response Normalization
```python
def _normalize_response(raw_data, check_in, check_out):
    """Convert Amadeus response to list of dicts for scorer."""
    num_nights = max((check_out - check_in).days, 1)
    hotels = []
    for item in raw_data:
        hotel_info = item.get("hotel", {})
        offers = item.get("offers", [])
        if not offers:
            continue
        offer = offers[0]  # Take cheapest/first offer
        price_total = float(offer.get("price", {}).get("total", "0"))

        cancellation_policies = offer.get("policies", {}).get("cancellations", [])
        free_cancel = any(
            p.get("type") == "FULL_REFUND" for p in cancellation_policies
        )

        hotels.append({
            "id": hotel_info.get("hotelId", "unknown"),
            "name": hotel_info.get("name", "Unknown Hotel"),
            "price_per_night": price_total / num_nights,
            "rating": hotel_info.get("rating"),  # Often None in sandbox
            "distance_km": 0.0,  # Not available from offers endpoint
            "free_cancellation": free_cancel,
            "amenities": [],  # Not in offers response
        })
    return hotels
```

### Mock Data Structure
```python
def get_mock_hotels() -> list[dict]:
    """Realistic Berlin hotel results matching Amadeus response structure."""
    return [
        {
            "id": "RTBERMD01",
            "name": "Motel One Berlin-Alexanderplatz",
            "price_per_night": 89.0,
            "rating": 4.3,
            "distance_km": 0.3,
            "free_cancellation": True,
            "amenities": ["wifi", "breakfast"],
        },
        {
            "id": "RTBERMD02",
            "name": "Generator Berlin Mitte",
            "price_per_night": 62.0,
            "rating": 3.6,
            "distance_km": 1.2,
            "free_cancellation": False,
            "amenities": ["wifi"],
        },
        # ... 4-6 more hotels with varied attributes
    ]
```

### Top-Level search_hotels Function
```python
def search_hotels(destination, check_in, check_out, guests, max_price):
    """Fetch hotels from API or fall back to mock data.

    Returns:
        tuple: (list[dict], bool) — hotel dicts and is_mock flag.
    """
    client = _get_client()
    if client is None:
        return get_mock_hotels(), True

    try:
        raw = _call_amadeus(client, destination, check_in, check_out, guests, max_price)
        hotels = _normalize_response(raw, check_in, check_out)
        if not hotels:
            return get_mock_hotels(), True
        return hotels, False
    except Exception:
        return get_mock_hotels(), True
```
</code_examples>

<sota_updates>
## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hotel Search v2 (single endpoint) | Hotel Search v3 (two-step: list + offers) | 2023 | Must call Hotel List first to get IDs, then Hotel Offers Search |
| Hotel Booking v1 | Hotel Booking v2 | 2023 | Different payload structure — relevant for Phase 4 |
| `amadeus` SDK v7 | `amadeus` SDK v9+ | 2024 | Added Hotel v3 endpoints, maintained backward compat |

**Deprecated/outdated:**
- **Hotel Search v2 single-call:** The old `/v2/shopping/hotel-offers` that accepted `cityCode` directly is deprecated. Must use v3 two-step flow.
- **`amadeus.shopping.hotel_offers.get(cityCode=...)`**: No longer works — use `reference_data.locations.hotels.by_city` + `shopping.hotel_offers_search`.
</sota_updates>

<open_questions>
## Open Questions

1. **Amadeus SDK timeout configuration**
   - What we know: The SDK uses `urllib` internally. There is no documented `timeout` parameter in `Client()`.
   - What's unclear: Whether newer versions (9.x) expose a timeout config, or if we need an external timeout mechanism.
   - Recommendation: Test during execution. If SDK doesn't support timeout, use `signal.alarm(5)` on Unix or `threading.Timer` as a fallback. For the hackathon demo, a simple try/except may suffice since the sandbox is typically fast.

2. **Amadeus sandbox data quality for Berlin**
   - What we know: Sandbox has synthetic data. Berlin (`BER`) generally returns results. Fields like `rating` are often missing.
   - What's unclear: Exact number of results and which fields are populated in current sandbox.
   - Recommendation: During execution, make one test call to verify. The defensive normalization + mock fallback handles any data gaps.

3. **`priceRange` parameter behavior**
   - What we know: The SDK docs mention `priceRange` as a filter. Format appears to be `"MIN-MAX"`.
   - What's unclear: Whether this is per-night or total stay, and whether the sandbox respects it.
   - Recommendation: Include the parameter but don't rely on it for filtering. Phase 3 scoring will naturally rank expensive hotels lower.
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [amadeus PyPI page](https://pypi.org/project/amadeus/) — SDK installation, initialization, all hotel endpoints, error classes
- [amadeus4dev/amadeus-python](https://github.com/amadeus4dev/amadeus-python) — SDK source: `_hotel_offers_search.py` (GET `/v3/shopping/hotel-offers`), `_by_city.py` (GET `/v1/reference-data/locations/hotels/by-city`), `errors.py` (ResponseError, NetworkError, ServerError, ClientError, AuthenticationError, NotFoundError)
- [amadeus4dev/amadeus-code-examples](https://github.com/amadeus4dev/amadeus-code-examples) — `hotel_search/v3/get/hotel_offers/Python SDK/hotel_search.py` verified two-step flow

### Secondary (MEDIUM confidence)
- Amadeus developer portal API reference — confirmed v3 hotel search requires hotelIds parameter (page is SPA, verified via SDK source)
- Amadeus SDK `response.py` — confirmed `response.data` extracts parsed JSON data key

### Tertiary (LOW confidence - needs validation)
- `priceRange` parameter format and sandbox behavior — inferred from SDK parameter name, needs testing during execution
- SDK timeout behavior — no documentation found, needs empirical testing
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Amadeus Python SDK (hotel search v3)
- Ecosystem: amadeus SDK, os.environ for credentials
- Patterns: Two-step search, response normalization, immediate fallback
- Pitfalls: Missing data fields, price normalization, city code mapping, timeout, rate limiting

**Confidence breakdown:**
- Standard stack: HIGH — SDK is official, well-documented, verified from source
- Architecture: HIGH — Two-step flow verified from SDK source and code examples
- Pitfalls: HIGH — Based on SDK source analysis and common API integration patterns
- Code examples: MEDIUM — Normalization code is based on SDK response structure analysis; exact sandbox response format needs validation during execution

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (30 days — Amadeus SDK is stable, hotel v3 API is established)
</metadata>

---

*Phase: 02-api-client-mock-fallback*
*Research completed: 2026-03-18*
*Ready for planning: yes*
