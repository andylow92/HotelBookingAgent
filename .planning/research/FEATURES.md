# Feature Research

**Domain:** Hotel Booking Provider Agent (API Integration Layer)
**Researched:** 2025-01-20
**Confidence:** HIGH (based on project README contract + domain knowledge)

## Feature Landscape

### Table Stakes (System Breaks Without These)

Features required for the hackathon demo to work. Missing any = demo fails.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Search API call** | Core demo flow starts with search | LOW | Wrap Amadeus Hotel Search API, parse response |
| **Weighted scoring engine** | The entire negotiation concept depends on this | MEDIUM | Implement formula from README: 5 dimensions, 0-1 normalization |
| **Top-3 result ranking** | Consumer Agent expects ranked options | LOW | Sort by total_score, slice top 3 |
| **Result tagging** | README specifies BEST_BALANCE, CHEAPEST, HIGHEST_RATED tags | LOW | Simple max() logic per dimension |
| **Score breakdown in response** | Consumer Agent needs this to explain to user | LOW | Return per-dimension scores alongside total |
| **Mock data fallback** | Demo must work even if Amadeus is down | LOW | Hardcoded realistic Berlin hotels in mock_data.py |
| **JSON request routing** | Consumer Agent sends action: search/book/cancel | LOW | Simple dispatcher function |
| **Re-score without re-fetch** | Core demo: weights change → new ranking instantly | MEDIUM | Cache raw API results, apply new weights on demand |
| **Data normalization** | API returns raw data; scoring needs 0-1 values | MEDIUM | Map prices, distances, ratings to normalized scores |

### Differentiators (Competitive Advantage for Demo)

Features that make the demo impressive but aren't strictly required to function.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Negotiation note generator** | Shows judge the AI "thinking" about tradeoffs | MEDIUM | Template-based: "Best balance is X% under budget and Y meters away. Cheapest drops rating to Z." |
| **Book operation** | Full CRUD shows production-readiness | LOW | Single API call; confirmation ID return |
| **Cancel operation** | Completes the lifecycle story | LOW | Single API call; refund status return |
| **Read booking** | Shows you can fetch existing reservations | LOW | Can cut if time runs out per README |
| **Graceful API error handling** | Demo doesn't crash on network blip | LOW | try/except → fall to mock data |
| **Clean score_breakdown format** | Makes Orca dashboard trace look professional | LOW | Already in JSON schema, just implement properly |

### Anti-Features (Do NOT Build for Hackathon)

Features that seem useful but waste hackathon time or add risk.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Multiple hotel API providers** | "What if Amadeus is down?" | Doubles integration time; mock data solves this | Mock data fallback handles API failure |
| **Rate limiting with backoff** | "Production systems need this" | Amadeus sandbox is generous; adds complexity | Simple try/catch, use mock on failure |
| **Redis/database caching** | "Cache for performance" | External dependency; demo is single-request | In-memory dict for re-scoring cache |
| **Authentication/sessions** | "Real booking needs auth" | Out of scope per PROJECT.md; Orca handles | Skip entirely |
| **HTTP REST endpoints** | "APIs need REST" | Orca wraps functions directly; REST is overhead | Python functions only |
| **Pagination** | "What if 1000 results?" | Amadeus returns manageable sets; we show top 3 | Hard limit to first 15 results |
| **Complex filtering logic** | "Let users filter by wifi, pool, etc." | Consumer Agent handles preferences via weights | Pass hard_constraints only (max_price) |
| **Price negotiation/bidding** | "Negotiate prices with hotels" | APIs don't support this; fake feature | Scoring IS the "negotiation" metaphor |
| **Real-time availability checks** | "Verify before booking" | Sandbox doesn't reflect real inventory | Trust API response at search time |
| **Unit test suite** | "Test-driven development" | 2-hour window; manual testing faster | Manual testing with hardcoded requests |
| **Logging infrastructure** | "Observability" | Print statements are enough for demo | print() for debugging |
| **Config files/environment vars** | "12-factor app" | Single hardcoded API key is fine | Inline constants |
| **Async/concurrent API calls** | "Performance" | Single search is fast enough | Sync calls are simpler |
| **Weather API integration** | README mentions this | Person C's scope, not Provider Agent | Explicitly out of scope |

## Feature Dependencies

```
[Search API Call]
    └──requires──> [Data Normalization]
                       └──enables──> [Weighted Scoring Engine]
                                         └──enables──> [Top-3 Ranking]
                                                           └──enables──> [Result Tagging]

[Mock Data Fallback] ──substitutes──> [Search API Call]

[Re-score Without Re-fetch]
    └──requires──> [Cached Raw Results]
    └──requires──> [Weighted Scoring Engine]

[Negotiation Note Generator]
    └──requires──> [Score Breakdown]
    └──enhances──> [Top-3 Ranking]

[Book Operation] ──independent──> [Search] (uses option_id from search)
[Cancel Operation] ──requires──> [Book Operation] (uses booking_id)
[Read Booking] ──requires──> [Book Operation] (uses booking_id)
```

### Dependency Notes

- **Scoring requires normalization:** Raw API prices (€89) must become 0-1 scores before weighting works
- **Re-scoring requires caching:** Can't change weights without stored raw data to re-process
- **Negotiation notes require score breakdown:** Can't explain "41% under budget" without per-dimension scores
- **Cancel requires booking_id:** Must book something first to have an ID to cancel

## MVP Definition

### Launch With (Hackathon Demo)

Minimum to pass the demo checkpoint at 19:45:

- [x] **Search API wrapper** — Call Amadeus, get hotel results
- [x] **Data normalization** — Transform API response to scorable format
- [x] **Scoring engine** — 5-dimension weighted formula from README
- [x] **Top-3 ranking + tagging** — BEST_BALANCE, CHEAPEST, HIGHEST_RATED
- [x] **Mock data fallback** — Berlin hotels ready if API fails
- [x] **JSON action router** — Dispatch search/book/cancel to right handler
- [x] **Re-score on weight change** — Core negotiation feature

### Add After Core Works (20:15-20:40)

Features to add in the polish phase:

- [ ] **Negotiation note generator** — Tradeoff explanations (judge impresser)
- [ ] **Book operation** — Create booking, return confirmation
- [ ] **Cancel operation** — Cancel booking, return refund status
- [ ] **Error handling** — Graceful fallback to mock data

### Cut If Running Out of Time

Per README priority, cut in this order:

- [ ] **Read booking** — "Show my booking" can be skipped; just show confirmation from book step
- [ ] **Fancy response formatting** — Raw JSON is fine if time is tight
- [ ] **Cancel flow** — Mention "cancellation works the same way" in demo

## Feature Prioritization Matrix

| Feature | Demo Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Weighted scoring engine | HIGH | MEDIUM | **P1** |
| Search API wrapper | HIGH | LOW | **P1** |
| Data normalization | HIGH | MEDIUM | **P1** |
| Re-score without re-fetch | HIGH | LOW | **P1** |
| Mock data fallback | HIGH (risk mitigation) | LOW | **P1** |
| Top-3 ranking + tagging | HIGH | LOW | **P1** |
| Negotiation note generator | HIGH (judge impresser) | MEDIUM | **P1** |
| Book operation | MEDIUM | LOW | **P2** |
| Cancel operation | MEDIUM | LOW | **P2** |
| Graceful error handling | MEDIUM | LOW | **P2** |
| Read booking | LOW | LOW | **P3** |
| Score breakdown formatting | LOW | LOW | **P3** |

**Priority key:**
- **P1:** Must work by 19:45 checkpoint
- **P2:** Add in 20:15-20:40 polish phase
- **P3:** Nice to have, cut first if behind

## Scoring Engine Specification

The scoring formula is the intellectual core. Get this right.

### Formula Implementation

```python
def calculate_score(hotel, weights, constraints):
    # Price: lower is better
    price_score = 1 - (hotel.price / constraints.max_price)
    
    # Location: closer is better (assume 5km max relevant distance)
    location_score = 1 - (hotel.distance_km / 5.0)
    
    # Rating: higher is better (out of 5)
    rating_score = hotel.rating / 5.0
    
    # Cancellation: free=1.0, paid=0.3, none=0.0
    cancellation_score = {
        'free': 1.0,
        'paid': 0.3,
        'none': 0.0
    }[hotel.cancellation_policy]
    
    # Amenities: fraction of desired amenities present
    amenities_score = len(hotel.amenities & desired_amenities) / len(desired_amenities)
    
    # Weighted sum
    total = (
        price_score * weights.price +
        location_score * weights.location +
        rating_score * weights.rating +
        cancellation_score * weights.cancellation +
        amenities_score * weights.amenities
    )
    
    return total, {
        'price': price_score,
        'location': location_score,
        'rating': rating_score,
        'cancellation': cancellation_score,
        'amenities': amenities_score
    }
```

### Tagging Logic

```python
def assign_tags(scored_hotels):
    best_balance = max(scored_hotels, key=lambda h: h.total_score)
    cheapest = min(scored_hotels, key=lambda h: h.price)
    highest_rated = max(scored_hotels, key=lambda h: h.rating)
    
    best_balance.tag = "BEST_BALANCE"
    if cheapest != best_balance:
        cheapest.tag = "CHEAPEST"
    if highest_rated != best_balance and highest_rated != cheapest:
        highest_rated.tag = "HIGHEST_RATED"
```

## Negotiation Note Templates

Pre-built templates for the note generator:

```python
templates = {
    'best_vs_cheapest': "Best balance is {pct_under}% under budget and {distance}m walk. Cheapest drops to {cheap_rating}★ rating and {cheap_distance}km distance.",
    'cancellation_warning': "Free cancellation only on options {options_with_free}.",
    'price_ceiling': "Highest rated hits near price ceiling at €{price}/night.",
    'amenities_tradeoff': "Option 1 includes {amenities}, but Option 2 lacks {missing}.",
}
```

## API Response Mapping

How Amadeus response fields map to our scoring model:

| Amadeus Field | Our Field | Transformation |
|---------------|-----------|----------------|
| `offers[0].price.total` | `price_per_night` | Parse float, divide by nights |
| `hotel.name` | `name` | Direct copy |
| `hotel.hotelId` | `id` | Prefix with "hotel_" |
| `hotel.geoCode.latitude/longitude` | `distance_km` | Haversine from preferred_area |
| `hotel.rating` | `rating` | Parse int, or default 3.0 |
| TBD | `free_cancellation` | Check cancellation policies |
| TBD | `amenities` | Map from room/hotel amenities |

**Note:** Exact field mapping depends on Amadeus API version. Build mock_data.py first, then adapt to real API.

## Sources

- **Project README.MD:** Scoring formula, message formats, demo script, cut priorities
- **PROJECT.md:** Scope boundaries, constraints, key decisions
- **Domain knowledge:** Hotel booking API patterns (Amadeus, Booking.com, Expedia documented patterns)

---
*Feature research for: TravelNeg Provider Agent*
*Researched: 2025-01-20*
*Confidence: HIGH — project contract is well-defined in README*
