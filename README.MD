# TravelNeg — AI Travel Negotiator

## Team Battle Plan

---

## What we're building

Two AI agents that talk to each other through Orca to help a user find and book travel services — hotels, restaurants, events, or tours (assigned on hackathon day):

1. **Consumer Agent** — talks to the user, understands what they want, converts vague preferences into scoring weights, enriches requests with weather and location data
2. **Provider Agent** — talks to the assigned travel API, scores every option with those weights, handles booking and cancellation

The magic trick: when the user changes their mind ("actually I need free cancellation"), the Consumer Agent re-weights, the Provider Agent re-scores, and the recommendation updates instantly. That negotiation loop between the two agents is what makes this project stand out.

**Bonus API integrations** (work across all domains):
- **Weather API** (OpenWeatherMap) — Consumer enriches recommendations with forecast data ("it'll rain Thursday, pick somewhere with indoor options")
- **Geocoding API** (OpenStreetMap Nominatim) — Provider computes real distances for location scoring instead of relying on API-provided data

---

## Domain-agnostic design

We don't know which domain we'll be assigned. The scoring engine is generic — only the dimension labels and normalization change per domain.

### Scoring dimensions by domain

| Dimension | Hotels | Restaurants | Events | Tours |
|---|---|---|---|---|
| **price** | price per night vs budget | price per person vs budget | ticket price vs budget | tour price vs budget |
| **location** | distance to preferred area | distance to user location | distance to user location | distance to meeting point |
| **rating** | guest rating / 5.0 | guest rating / 5.0 | event rating / 5.0 | tour rating / 5.0 |
| **flexibility** | free cancellation | reservation flexibility | refund policy | cancellation policy |
| **match** | amenities matched | cuisine/dietary match | category/interest match | language/group size match |

The formula is always the same:

```
score = (price_score × w_price)
      + (location_score × w_location)
      + (rating_score × w_rating)
      + (flexibility_score × w_flexibility)
      + (match_score × w_match)
```

All weights sum to 1.0. The Consumer Agent sets them from user intent. The Provider Agent applies them.

### How each component is scored (0 to 1)

| Component | Formula | Example (hotel) | Example (restaurant) |
|---|---|---|---|
| price_score | 1 − (price / max_budget) | €89/€150 → 0.59 | €25/€50 → 0.50 |
| location_score | 1 − (distance_km / max_distance) | 0.3km/5km → 0.94 | 0.8km/3km → 0.73 |
| rating_score | rating / 5.0 | 4.3/5.0 → 0.86 | 4.7/5.0 → 0.94 |
| flexibility_score | free=1.0, partial=0.3, none=0.0 | Free cancel → 1.0 | Walk-in ok → 1.0 |
| match_score | matched_features / desired_features | 2/3 amenities → 0.67 | 2/2 dietary → 1.0 |

**location_score uses real distance** computed via Geocoding API (Nominatim), not hardcoded.

### How the Consumer Agent sets weights

| User says | What changes |
|---|---|
| "cheapest possible" | price → 0.55, reduce others |
| "best location" / "near X" | location → 0.45 |
| "highest rated" | rating → 0.45 |
| "I might cancel" / "need flexibility" | flexibility → 0.40 |
| "I need [specific features]" | match → 0.25 |
| "don't care about X" | X → 0.0, redistribute |

Default balanced weights: price=0.25, location=0.25, rating=0.20, flexibility=0.15, match=0.15

---

## How it works end-to-end

```
User: "Find me something in Berlin, under €150, near Alexanderplatz, arriving late Thursday"
                              ↓
        ┌─────────────────────────────────────────┐
        │  CONSUMER AGENT                         │
        │  1. Extracts constraints from NL        │
        │  2. Calls Weather API for Berlin Thu-Sat│
        │  3. Sets weights from user intent       │
        │  4. Sends structured JSON via Orca      │
        │     (includes weather context)          │
        └─────────────┬───────────────────────────┘
                      ↓
        ┌─────────────────────────────────────────┐
        │  PROVIDER AGENT                         │
        │  1. Calls assigned travel API           │
        │  2. Calls Geocoding API for distances   │
        │  3. Scores each result with weights     │
        │  4. Returns top 3 + negotiation note    │
        │     (includes weather-aware suggestions)│
        └─────────────┬───────────────────────────┘
                      ↓
        ┌─────────────────────────────────────────┐
        │  CONSUMER AGENT                         │
        │  Reads scores + negotiation note        │
        │  Incorporates weather into explanation   │
        │  Presents recommendation to user        │
        └─────────────────────────────────────────┘
                      ↓
User: "Wait, I might need to cancel. Need free cancellation."
                      ↓
        Consumer re-weights: flexibility 0.15 → 0.40
        Sends updated request → Provider re-scores → new #1 emerges
```

---

## External API integrations (bonus points)

These work regardless of which domain we're assigned:

### 1. Weather API — OpenWeatherMap (free tier)

**Purpose:** Enrich recommendations with weather context.

**How it's used:**
- Consumer Agent calls Weather API when it extracts destination + dates
- Forecast is included in the request context sent to Provider
- Provider can factor weather into its negotiation note
- Consumer uses it when presenting results to the user

**Examples by domain:**

| Domain | Weather adds value |
|---|---|
| Hotels | "It'll rain Thursday — top pick has indoor pool and spa" |
| Restaurants | "Sunny and 22°C — recommending places with terraces" |
| Events | "Rain forecast Saturday — outdoor events scored lower" |
| Tours | "Cold morning expected — indoor museum tour ranked higher" |

**API call:**
```
GET https://api.openweathermap.org/data/2.5/forecast
  ?q={destination}
  &appid={API_KEY}
  &units=metric
  &cnt=8  (next 24h in 3h intervals)
```

**Token efficiency:** We extract only `temp`, `weather[0].main`, and `rain` from the response. ~50 tokens added to context vs ~2000 raw.

### 2. Geocoding API — OpenStreetMap Nominatim (free, no key)

**Purpose:** Compute real distances for location scoring.

**How it's used:**
- Provider Agent geocodes the user's preferred area to get lat/lon
- Provider geocodes each result's address to get lat/lon
- Haversine formula computes real distance in km
- Distance feeds into `location_score = 1 − (distance_km / max_distance)`

**API call:**
```
GET https://nominatim.openstreetmap.org/search
  ?q={address}, {city}
  &format=json
  &limit=1
```

**Distance formula:**
```python
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))
```

**Rate limit:** Nominatim allows 1 req/sec. We cache the preferred area coordinates and batch-geocode results. For 15 results this takes ~15s — acceptable for a demo. Fallback: if too slow, use mock coordinates.

---

## CRUD operations we need to demo

| Operation | What the user says | What happens |
|---|---|---|
| **Search** | "Find me a [hotel/restaurant/event/tour] in Berlin" | Consumer extracts constraints → Provider calls API → scores → returns top 3 |
| **Book** | "Book the first one" | Consumer sends book request → Provider calls API create endpoint → returns confirmation |
| **Read** | "Show my booking" | Consumer requests details → Provider calls API with booking ID → returns info |
| **Cancel** | "Cancel it" | Consumer confirms → Provider calls API cancel endpoint → returns status |

All four need to work in the demo.

---

## Message format between agents

### Consumer → Provider (via Orca)

```json
{
  "action": "search",
  "domain": "hotels",
  "destination": "Berlin",
  "date_start": "2026-03-19",
  "date_end": "2026-03-21",
  "guests": 1,
  "hard_constraints": {
    "max_price": 150,
    "currency": "EUR"
  },
  "weights": {
    "price": 0.25,
    "location": 0.30,
    "rating": 0.20,
    "flexibility": 0.15,
    "match": 0.10
  },
  "context": {
    "preferred_area": "Alexanderplatz",
    "preferred_area_coords": { "lat": 52.5219, "lon": 13.4132 },
    "weather": {
      "summary": "Rain expected Thursday, 8°C. Clearing Friday, 14°C.",
      "thursday": { "temp": 8, "condition": "Rain" },
      "friday": { "temp": 14, "condition": "Clear" }
    },
    "desired_features": ["wifi", "breakfast"]
  }
}
```

For booking:
```json
{
  "action": "book",
  "option_id": "item_abc123",
  "guest_name": "...",
  "date_start": "2026-03-19",
  "date_end": "2026-03-21"
}
```

For cancellation:
```json
{
  "action": "cancel",
  "booking_id": "BK-4821"
}
```

### Provider → Consumer (via Orca)

```json
{
  "action": "search_results",
  "options": [
    {
      "id": "item_abc123",
      "name": "Motel One Berlin-Alexanderplatz",
      "price": 89,
      "rating": 4.3,
      "distance_km": 0.3,
      "flexibility": "free",
      "matched_features": ["wifi", "breakfast"],
      "total_score": 0.87,
      "score_breakdown": {
        "price": 0.59,
        "location": 0.94,
        "rating": 0.86,
        "flexibility": 1.0,
        "match": 0.67
      },
      "tag": "BEST_BALANCE"
    },
    {
      "id": "item_def456",
      "name": "Generator Berlin Mitte",
      "price": 62,
      "total_score": 0.81,
      "tag": "CHEAPEST"
    },
    {
      "id": "item_ghi789",
      "name": "Hotel Indigo Berlin",
      "price": 142,
      "total_score": 0.79,
      "tag": "HIGHEST_RATED"
    }
  ],
  "negotiation_note": "Best balance is 41% under budget and 300m walk. Cheapest drops to 3.6 rating and 1.2km. Highest rated hits near price ceiling. Free cancellation only on options 1 and 3. Note: rain expected Thursday — top pick has indoor facilities.",
  "apis_used": ["assigned_travel_api", "nominatim_geocoding"]
}
```

The `negotiation_note` is key — it's the Provider explaining tradeoffs to the Consumer. This is what shows up in Orca's trace and impresses judges.

---

## Work split

### Person A — Consumer Agent

**You own:** Everything between the user and Orca.

Build:
- System prompt that makes the LLM extract constraints from natural language
- Weight engine: takes user phrases → outputs weight dictionary (domain-agnostic)
- Weather API client: fetches forecast for destination + dates, extracts summary
- Geocoding call: resolves preferred_area to lat/lon coordinates
- Response formatter: takes scored results + weather → writes a human-friendly recommendation
- Follow-up handler: detects changed constraints → re-weights → re-sends to Provider
- Confirmation flow: asks "want me to book?" before sending book/cancel actions

Test independently with:
- Hardcoded mock responses from the Provider (use the JSON above)
- Verify: different user inputs produce different weights
- Verify: changing a constraint mid-conversation triggers a re-request
- Verify: weather data appears in the context sent to Provider

**Deliverable:** Consumer agent that registers with Orca, enriches requests with weather + geocoding, sends structured JSON, and handles responses.

---

### Person B — Provider Agent

**You own:** Everything between Orca and the assigned travel API.

Build:
- API client: wrapper around the assigned travel API (search, book, cancel endpoints) — adapts to whichever domain we're given
- Geocoding client: resolves each result's address to lat/lon via Nominatim, computes distance using haversine
- Scoring engine: takes API results + weights → calculates scores → ranks → tags top 3 (generic formula, domain-specific normalization)
- Negotiation note generator: writes a brief explanation of tradeoffs (uses weather context if provided)
- CRUD handler: routes actions (search/book/read/cancel) to the right API call
- Mock data fallback: if the API is slow or down, return realistic fake results

Test independently with:
- Hardcoded requests (use the JSON above as input)
- Verify: changing weights produces different rankings
- Verify: geocoding returns sensible distances
- Verify: booking and cancellation return proper confirmations

**Deliverable:** Provider agent that registers with Orca, receives structured JSON, calls the API + geocoding, and returns scored results.

---

### Person C — Orca integration + demo

**You own:** Making the two agents talk to each other, and the demo.

Build:
- Orca SDK setup: register both agents, configure message routing
- Domain config: single config file that switches field names per assigned domain
- End-to-end testing: send a user message → verify it flows through Consumer → Orca → Provider → back
- Simple chat interface (terminal or Streamlit — nothing fancy)
- Demo script rehearsal

Test:
- Full flow works: search → results → re-negotiation → book → cancel
- Weather and geocoding data visible in Orca message trace
- Orca dashboard shows clean agent trace with all messages visible
- Demo runs within 3–5 minutes

**Deliverable:** Working end-to-end system + polished demo.

---

## Timeline (19:00 – 21:00)

| Time | Person A (Consumer) | Person B (Provider) | Person C (Orca + Demo) |
|---|---|---|---|
| 19:00–19:20 | Prompt engineering + weight engine | API client + mock data (adapt to assigned domain) | Orca SDK setup + domain config |
| 19:20–19:45 | Parse → JSON + Weather API call | Score engine + Geocoding integration | Connect agents via Orca |
| 19:45–20:15 | Re-negotiation logic | CRUD (book + cancel) | First end-to-end test |
| 20:15–20:40 | Edge cases + weather in responses | Edge cases + distance polish | Full flow test + API trace check |
| 20:40–21:00 | Help with demo | Help with demo | Rehearse demo script |

**Checkpoint at 19:45:** Both agents MUST be independently testable by now. If not, cut scope.

---

## Demo script (3–5 min)

*Example shown with hotels — adapt language to assigned domain.*

### Turn 1 — Search (60s)
> **User:** "Find me a hotel in Berlin next Thursday to Saturday. Under €150 per night, near Alexanderplatz."

Show: Consumer parsing → Weather API call → Geocoding → JSON in Orca → Provider scoring with real distances → 3 results returned

> **Agent:** "Top pick: Motel One at €89/night — 300m from Alexanderplatz, rated 4.3, 41% under your budget. Heads up: rain expected Thursday evening, but this hotel has indoor pool and lounge."

### Turn 2 — Re-negotiation (60s)
> **User:** "I might cancel this trip. Need free cancellation. Also, breakfast included."

Show: weights shift in Orca → Provider re-scores → new #1

> **Agent:** "Updated recommendation: Hampton by Hilton at €112/night. Free cancellation and breakfast included. Previous pick didn't have free cancellation."

### Turn 3 — Book (45s)
> **User:** "Book it."

Show: book request in Orca → Provider calls API → confirmation

> **Agent:** "Booked! Confirmation #HBB-4821. Free cancellation until March 18."

### Turn 4 — Cancel (30s)
> **User:** "Trip is off. Cancel."

Show: cancel in Orca → done

> **Agent:** "Cancelled. Full refund processing."

### Turn 5 — Show Orca dashboard (30s)
Open Orca. Point at:
- The full message trace
- Weather data flowing from Consumer to Provider
- Real distances computed via Geocoding
- The negotiation_note where Provider explains tradeoffs
- The weight change when user asked for flexibility
- **3 APIs integrated:** assigned travel API + OpenWeatherMap + Nominatim

---

## Folder structure

```
travelneg/
├── consumer_agent/
│   ├── agent.py           # Person A: main agent logic
│   ├── weight_engine.py   # Person A: NL → weights (domain-agnostic)
│   ├── weather_client.py  # Person A: OpenWeatherMap integration
│   ├── geocoding.py       # Shared: Nominatim geocoding + haversine
│   └── prompts.py         # Person A: system prompts
├── provider_agent/
│   ├── agent.py           # Person B: main agent logic
│   ├── api_client.py      # Person B: travel API wrapper (adapts to domain)
│   ├── scorer.py          # Person B: generic scoring formula
│   └── mock_data.py       # Person B: fallback data per domain
├── shared/
│   ├── models.py          # Shared: Pydantic models for messages
│   ├── domain_config.py   # Person C: domain-specific field mappings
│   └── orca_config.py     # Person C: Orca SDK setup
├── app.py                 # Person C: chat interface
├── requirements.txt
└── README.md
```

---

## What to cut if running out of time

**Priority order (cut from bottom first):**

1. Geocoding API (use mock distances) ← cut this first
2. Weather API integration (remove weather from context)
3. Read booking details (just show confirmation from the book step)
4. Cancel flow (mention "cancellation works the same way" in demo)
5. Fancy response formatting
6. ~~Search + Scoring + Re-negotiation~~ ← NEVER cut this, it's the whole point

**Minimum viable demo:** User says something → Consumer extracts constraints and weights → Provider scores results → recommendation shown → user changes mind → re-negotiation produces new ranking. That's enough to win if it works cleanly.

---

## Risk plan

| Problem | Solution |
|---|---|
| Assigned domain we didn't expect | Scoring is generic. Only api_client.py and mock_data.py need domain-specific adaptation (~20 min). |
| Travel API is down or slow | Person B has mock_data.py ready. Swap in 2 minutes. |
| Weather API key missing/rate-limited | Hardcode a realistic forecast for the demo city. Consumer still sends weather context. |
| Nominatim rate limit (1 req/sec) | Cache preferred area coords. For 15 results, pre-geocode in batch. Fallback: mock coordinates. |
| Orca won't connect | Person C falls back to direct function calls. Explain in demo "this would be Orca-routed." |
| LLM is rate-limited | Cache the first successful search. Demo from cache. |
| Team member gets stuck | Everyone tests independently first. Consumer works with mock Provider. Provider works with hardcoded requests. |
| Don't finish CRUD | Search + scoring + re-negotiation is the minimum. See "what to cut" above. |

---

## APIs used (for judging)

| # | API | Purpose | Who calls it |
|---|---|---|---|
| 1 | Assigned travel API (hotel/restaurant/event/tour) | Core CRUD — search, book, read, cancel | Provider Agent |
| 2 | OpenWeatherMap Forecast API | Weather-aware recommendations | Consumer Agent |
| 3 | OpenStreetMap Nominatim | Real distance calculation for location scoring | Provider Agent |

3 APIs integrated. Judging criteria: "Number and relevance of travel APIs used."

---

## One-liner for the pitch

> Two AI agents negotiate travel bookings for you — one understands what you want (and checks the weather), the other finds the best deal (with real distances). They talk to each other through Orca so you never have to fill a booking form again.
