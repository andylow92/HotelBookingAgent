# Pitfalls Research

**Domain:** Hotel Booking API Integration (Provider Agent for TravelNeg)
**Researched:** 2025-01-18
**Confidence:** MEDIUM-HIGH (based on Amadeus documentation patterns, Python API best practices, and common scoring algorithm failures)

## Critical Pitfalls

### Pitfall 1: Amadeus Sandbox Returns Fake Data That Breaks Your Scoring

**What goes wrong:**
Amadeus test environment returns synthetic hotel data with placeholder values: prices of €0.00 or €9999.00, distances of 0.0km, ratings of 0.0 or null, and missing amenity arrays. Your scoring formula produces NaN, infinity, or nonsensical rankings.

**Why it happens:**
Developers test with sandbox, see "it works," but don't notice the data is garbage. The scoring formula `1 - (price / max_budget)` produces `1.0` when price is 0, making every free hotel rank #1. Division by max_distance of 0 crashes. Null ratings fail.

**How to avoid:**
1. Add defensive checks in `scorer.py` before every calculation:
   ```python
   # Safe scoring with defaults
   price_score = 1 - (min(price, max_budget) / max_budget) if price > 0 else 0.5
   location_score = 1 - (distance / max_distance) if max_distance > 0 else 0.5
   rating_score = rating / 5.0 if rating and rating > 0 else 0.5
   ```
2. Clamp all scores to 0.0–1.0 range after calculation
3. Log warnings when using fallback values

**Warning signs:**
- All hotels have identical scores
- Score breakdown shows 1.0 or 0.0 for every component
- Hotels with "best" scores have absurd prices (€0 or €9999)

**Phase to address:**
Phase 1 (Scorer Implementation) — build defensive scoring from day one

---

### Pitfall 2: Mock Data Shape Doesn't Match Amadeus Response Shape

**What goes wrong:**
You build `mock_data.py` with a clean structure you invented. When real API returns data, field names differ (`hotelId` vs `hotel_id`, nested `offers[0].price.total` vs flat `price_per_night`), and your code crashes. Demo fails.

**Why it happens:**
Amadeus Hotel Search returns deeply nested JSON with camelCase fields. Developers create mock data matching their internal models, not the API's actual response format.

**Example of real Amadeus Hotel Offers response structure:**
```json
{
  "data": [
    {
      "hotel": {
        "hotelId": "HSMIABC1",
        "name": "Motel One Berlin",
        "rating": "4"  // String, not number!
      },
      "offers": [
        {
          "price": {
            "total": "89.00",  // String, not number!
            "currency": "EUR"
          },
          "policies": {
            "cancellation": { "type": "FULL_REFUNDABLE" }
          }
        }
      ]
    }
  ]
}
```

**How to avoid:**
1. **Start from real API docs** — use Amadeus Hotel Search API reference as source of truth
2. **Make mock data match real structure** — copy an actual response from Amadeus docs, then modify values
3. **Build a transformer layer** in `api_client.py` that normalizes both real and mock into your internal model:
   ```python
   def normalize_hotel_response(raw: dict) -> HotelResult:
       """Transforms Amadeus format → internal format. Works for both real and mock."""
       return HotelResult(
           id=raw["hotel"]["hotelId"],
           name=raw["hotel"]["name"],
           price_per_night=float(raw["offers"][0]["price"]["total"]),
           rating=float(raw["hotel"].get("rating", "0")),
           # ... etc
       )
   ```
4. **Mock at the normalized layer**, not at the raw layer — let transformer handle shape differences

**Warning signs:**
- KeyError exceptions when switching from mock to real API
- Tests pass but demo crashes
- `api_client.py` has different parsing logic for mock vs real

**Phase to address:**
Phase 1 (API Client) — define transformer from real Amadeus format immediately

---

### Pitfall 3: Rate Limit Exhaustion Mid-Demo

**What goes wrong:**
Amadeus free tier allows 10 requests/second and ~2,000/month. You hit the limit during demo rehearsal, then hit it again 5 minutes before the actual demo. API returns 429 errors and demo dies.

**Why it happens:**
- Developers make 50 test calls while debugging
- Demo rehearsal uses real API instead of mock
- No circuit breaker when rate limit hit

**How to avoid:**
1. **Track API call count** — add a counter in `api_client.py`:
   ```python
   API_CALLS_TODAY = 0
   def search_hotels(...):
       global API_CALLS_TODAY
       API_CALLS_TODAY += 1
       if API_CALLS_TODAY > 100:  # Warning threshold
           logger.warning(f"API calls today: {API_CALLS_TODAY}")
   ```
2. **Automatic mock fallback** — when 429 received, switch to mock:
   ```python
   try:
       response = amadeus.shopping.hotel_offers.get(...)
   except ResponseError as e:
       if e.response.status_code == 429:
           logger.warning("Rate limited, using mock data")
           return mock_search_results(params)
       raise
   ```
3. **Rehearse with mock mode flag** — `USE_MOCK=true python demo.py`
4. **Cache search results** — same search params → return cached response

**Warning signs:**
- 429 responses in logs
- Demo worked an hour ago, now fails
- Inconsistent behavior between team members

**Phase to address:**
Phase 1 (API Client) — build rate limit handling into initial implementation

---

### Pitfall 4: Division by Zero in Scoring Formula

**What goes wrong:**
Scoring formula divides by `max_budget`, `max_distance`, or `desired_amenities_count`. When any are 0 or None, Python raises ZeroDivisionError or returns infinity.

**Why it happens:**
- User doesn't specify budget → `max_budget = None`
- All hotels are at same location (distance = 0) → normalization fails
- User wants no amenities → `matched / desired` = `0/0`

**How to avoid:**
1. **Set sensible defaults** in scoring:
   ```python
   DEFAULT_MAX_BUDGET = 500  # Reasonable upper bound
   DEFAULT_MAX_DISTANCE = 10  # 10km
   
   def calculate_price_score(price: float, max_budget: float | None) -> float:
       budget = max_budget or DEFAULT_MAX_BUDGET
       return max(0.0, min(1.0, 1 - (price / budget)))
   ```
2. **Handle empty amenities gracefully**:
   ```python
   def calculate_amenities_score(matched: list, desired: list) -> float:
       if not desired:  # User didn't request any amenities
           return 1.0  # Full score — no requirements to meet
       return len(set(matched) & set(desired)) / len(desired)
   ```
3. **Use math.inf-safe comparisons** or always clamp results

**Warning signs:**
- ZeroDivisionError in logs
- Hotels with `inf` scores
- Sorting fails because `float('inf') > float('inf')` is False

**Phase to address:**
Phase 1 (Scorer) — add denominator guards from first implementation

---

### Pitfall 5: Weights Don't Sum to 1.0 After Re-negotiation

**What goes wrong:**
Consumer Agent changes one weight but forgets to redistribute others. Weights sum to 0.85 or 1.15. Scores become incomparable across re-negotiations.

**Why it happens:**
The README says "all weights must sum to 1.0" but there's no enforcement. Consumer Agent might send `{"price": 0.55, "location": 0.30, ...}` that sums to 1.10.

**How to avoid:**
1. **Validate on receipt** in Provider Agent:
   ```python
   def validate_weights(weights: dict) -> dict:
       total = sum(weights.values())
       if abs(total - 1.0) > 0.01:
           # Normalize automatically
           return {k: v / total for k, v in weights.items()}
       return weights
   ```
2. **Log warning** when normalization happens:
   ```python
   if abs(total - 1.0) > 0.01:
       logger.warning(f"Weights summed to {total}, normalized")
   ```
3. **Include normalized weights in response** so Consumer Agent knows what was actually used

**Warning signs:**
- Same search, same hotels, different scores without weight changes
- Debugging shows weights sum to ≠1.0
- Re-negotiation produces unexpected score changes

**Phase to address:**
Phase 1 (Scorer or Models) — weight validation belongs in shared models or scorer input validation

---

### Pitfall 6: Booking/Cancel Endpoints Don't Exist in Sandbox

**What goes wrong:**
Amadeus Hotel Booking API (POST /v1/booking/hotel-bookings) requires production credentials and real credit card. Sandbox doesn't support actual booking creation. Your book/cancel flow crashes.

**Why it happens:**
Developers assume sandbox has all endpoints. Amadeus sandbox only supports search (GET hotel-offers, GET hotel-offers-search). Booking/cancel require production access.

**How to avoid:**
1. **Mock booking entirely** — don't even try calling real booking endpoint:
   ```python
   def book_hotel(option_id: str, guest: str, ...) -> BookingConfirmation:
       # Always mock in hackathon — no real booking API access
       return BookingConfirmation(
           booking_id=f"BK-{random.randint(1000, 9999)}",
           hotel_id=option_id,
           status="CONFIRMED",
           ...
       )
   ```
2. **Design mock to match expected real response shape** — use Amadeus booking docs for structure
3. **Be transparent in demo** — "booking uses simulated confirmation for demo purposes"

**Warning signs:**
- 403 Forbidden on booking calls
- Documentation says "production only"
- Trying to figure out booking auth that doesn't exist

**Phase to address:**
Phase 1 (API Client) — don't even attempt real booking, mock from start

---

### Pitfall 7: String vs. Number Type Mismatches from API

**What goes wrong:**
Amadeus returns prices as strings ("89.00"), ratings as strings ("4"), and booleans as strings ("true"). Your Pydantic models expect `float` and `bool`. Validation fails or comparisons break.

**Why it happens:**
JSON doesn't have strong typing. Hotel APIs often return everything as strings for "safety." Python code assumes proper types.

**How to avoid:**
1. **Use Pydantic validators** in `shared/models.py`:
   ```python
   from pydantic import validator
   
   class HotelOffer(BaseModel):
       price: float
       rating: float
       
       @validator('price', 'rating', pre=True)
       def coerce_to_float(cls, v):
           if isinstance(v, str):
               return float(v) if v else 0.0
           return v or 0.0
   ```
2. **Test with stringified mock data** — make mock intentionally return strings to catch issues early
3. **Log coercions in development** — so you know when automatic conversion happens

**Warning signs:**
- ValidationError on API response parsing
- String comparisons instead of numeric ("100" < "20" is True!)
- TypeError in scoring calculations

**Phase to address:**
Phase 1 (Shared Models) — add validators when defining Pydantic models

---

### Pitfall 8: Re-scoring Triggers API Call Instead of Using Cached Results

**What goes wrong:**
User changes weights (re-negotiation). Provider Agent fetches fresh results from API instead of re-scoring cached hotels. Rate limit burns faster, latency increases, and results might change unexpectedly.

**Why it happens:**
Developers don't distinguish "search" from "re-score." Same endpoint handles both.

**How to avoid:**
1. **Cache results per search key**:
   ```python
   from functools import lru_cache
   
   @lru_cache(maxsize=10)
   def fetch_hotels(destination, check_in, check_out, max_price):
       # Expensive API call
       return amadeus.shopping.hotel_offers.get(...)
   
   def handle_search(request):
       # Fetch (or get from cache) based on search params
       raw_results = fetch_hotels(...)
       # Score with current weights (not cached)
       return score_and_rank(raw_results, request.weights)
   ```
2. **Explicit re-score action** — if Consumer sends same search params but different weights, skip API call:
   ```python
   if request.action == "rescore" and has_cached_results(request):
       return rescore_cached(request)
   ```

**Warning signs:**
- API calls double/triple during re-negotiation demo
- Different hotels appear after weight change (shouldn't change available hotels)
- Slow response on re-negotiation

**Phase to address:**
Phase 2 (CRUD Handler) — add caching when implementing action routing

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoding Amadeus credentials in code | Fast to get started | Security risk, can't share code | Never — use env vars from minute one |
| Single `if/else` chain for all CRUD | Fast to prototype | Unreadable, hard to extend | For 2-hour hackathon, acceptable |
| No logging | Fewer lines of code | Impossible to debug demo failures | Never — add basic logging from start |
| Synchronous API calls | Simpler code | Blocks entire agent during slow API | Acceptable for hackathon (simplicity > performance) |
| No retry logic | Simpler code | Flaky demo from transient failures | Risky — add 1-retry with backoff |

## Integration Gotchas

Common mistakes when connecting to Amadeus and external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Amadeus Auth | Hardcoding client_id/secret | Use `AMADEUS_CLIENT_ID` and `AMADEUS_CLIENT_SECRET` env vars |
| Amadeus Auth | Not handling token expiry | Amadeus SDK handles this, but if raw HTTP, refresh token every 30 min |
| Hotel Search | Passing city name instead of IATA code | Use "BER" not "Berlin" — or use multi-city search with cityCode lookup |
| Hotel Search | Not setting radius | Amadeus defaults to 5km which may return 0 results in dense cities — start with 10-15km |
| Date Handling | Using datetime instead of date string | Amadeus wants "2026-03-19" format exactly — use `.strftime('%Y-%m-%d')` |
| Currency | Assuming EUR everywhere | Check response currency, may differ from request — always display returned currency |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching all hotels then filtering | Works with 10 results | Use API-side filtering (priceRange, radius) | >50 results slow scoring |
| No caching | Fresh data every time | Cache by search params for 5 minutes | Rate limit on re-negotiations |
| Scoring in Python loop | Works for 20 hotels | Keep under 50 hotels, or use pandas/numpy for batches | >100 hotels noticeable lag |
| Logging every field | Good debugging | Log summaries, not full responses | Large responses fill logs |

## Security Mistakes

Domain-specific security issues.

| Mistake | Risk | Prevention |
|---------|------|------------|
| API credentials in code | Credential leak when code shared | `.env` file + `.gitignore` |
| Logging full API responses | May contain guest data in production | Log IDs and summaries only |
| Accepting any option_id for booking | Could forge booking requests | Validate option_id exists in recent search results |
| No input validation on guest_name | Injection attacks in production | Pydantic validation with string constraints |

## UX Pitfalls

Common user experience mistakes for demo flow.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing raw scores (0.87) without context | Numbers meaningless to user | "Scored 87/100 — best balance of your priorities" |
| Not explaining why #1 changed after re-negotiation | User confused | Negotiation note: "Now prioritizing cancellation, Hampton moved from #3 to #1" |
| Showing all score breakdowns | Information overload | Show total score + the 1-2 factors that made the difference |
| Returning error codes to user | "Error 429" unhelpful | "Taking a moment to find more options..." (graceful fallback) |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Scoring engine:** Works with perfect data — verify it handles null ratings, zero prices, missing amenities
- [ ] **Mock data:** Returns results — verify structure matches real Amadeus response exactly
- [ ] **API client:** Makes calls — verify it handles 429 rate limit, 500 errors, timeouts (add `timeout=10`)
- [ ] **Re-scoring:** Changes rankings — verify it doesn't re-fetch from API (check call count)
- [ ] **CRUD routing:** All actions work — verify invalid action type returns helpful error, not crash
- [ ] **Tags:** BEST_BALANCE assigned — verify CHEAPEST and HIGHEST_RATED are also computed and may differ from #1
- [ ] **Negotiation note:** Generated — verify it references actual differences between options, not generic text

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Rate limit exceeded | LOW | Flip `USE_MOCK=true`, continue demo with mock data |
| Scoring produces NaN | MEDIUM | Add `if math.isnan(score): score = 0.5` in scoring loop |
| Mock doesn't match API shape | HIGH | Copy actual Amadeus response from docs, rebuild mock |
| Booking fails in demo | LOW | Booking was already mock — check mock function returns proper shape |
| Weights don't sum to 1.0 | LOW | Add normalization on receive, runs automatically |
| Tags all show BEST_BALANCE | MEDIUM | Fix tag assignment logic — check cheapest/highest-rated separately |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Fake sandbox data breaks scoring | Phase 1 (Scorer) | Test with edge-case data: price=0, rating=null |
| Mock shape mismatch | Phase 1 (API Client) | Parse real Amadeus JSON sample before mocking |
| Rate limit exhaustion | Phase 1 (API Client) | Implement 429 handler with mock fallback |
| Division by zero | Phase 1 (Scorer) | Unit test with all denominators = 0 |
| Weights don't sum to 1.0 | Phase 1 (Scorer/Models) | Validation test with weights summing to 1.1 |
| Booking doesn't work in sandbox | Phase 1 (API Client) | Never attempt real booking — mock from start |
| String/number type mismatch | Phase 1 (Models) | Pydantic validators with stringified test data |
| Re-score triggers API | Phase 2 (CRUD Handler) | Count API calls during re-score test |

## Sources

- Amadeus for Developers documentation: Hotel Search API reference (structure of responses)
- Amadeus rate limiting documentation: Free tier limits (10 req/sec, limited monthly)
- Common Python API client patterns and Pydantic best practices
- Known hotel API integration patterns from travel tech domain
- Scoring algorithm edge cases from recommendation system design patterns

---
*Pitfalls research for: Hotel Booking Provider Agent (TravelNeg)*
*Researched: 2025-01-18*
