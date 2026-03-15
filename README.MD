# TravelNeg — Hotel Booking Negotiator

## Team Battle Plan

---

## What we're building

Two AI agents that talk to each other through Orca to help a user find and book a hotel:

1. **Consumer Agent** — talks to the user, understands what they want, converts vague preferences into scoring weights
2. **Provider Agent** — talks to the Hotel API, scores every option with those weights, handles booking and cancellation

The magic trick: when the user changes their mind ("actually I need free cancellation"), the Consumer Agent re-weights, the Provider Agent re-scores, and the recommendation updates instantly. That negotiation loop between the two agents is what makes this project stand out.

---

## How it works end-to-end

```
User: "Hotel in Berlin, under €150, near Alexanderplatz, arriving late Thursday"
                              ↓
        ┌─────────────────────────────────────────┐
        │  CONSUMER AGENT                         │
        │  Extracts:                              │
        │    destination = Berlin                 │
        │    max_price = 150 EUR                  │
        │    preferred_area = Alexanderplatz       │
        │    check_in = Thursday                  │
        │  Sets weights:                          │
        │    price=0.25, location=0.30,           │
        │    rating=0.20, cancellation=0.15,      │
        │    amenities=0.10                       │
        └─────────────┬───────────────────────────┘
                      ↓ (sends structured JSON via Orca)
        ┌─────────────────────────────────────────┐
        │  PROVIDER AGENT                         │
        │  1. Calls Hotel API with constraints    │
        │  2. Gets 15 results                     │
        │  3. Scores each with the formula        │
        │  4. Returns top 3 + negotiation note    │
        └─────────────┬───────────────────────────┘
                      ↓ (returns via Orca)
        ┌─────────────────────────────────────────┐
        │  CONSUMER AGENT                         │
        │  Reads scores + negotiation note        │
        │  Picks best, explains to user:          │
        │  "Motel One at €89 — best balance of    │
        │   price and location (300m away, 4.3★)" │
        └─────────────────────────────────────────┘
                      ↓
User: "Wait, I might need to cancel. Free cancellation required."
                      ↓
        Consumer re-weights: cancellation 0.15 → 0.40
        Sends updated request → Provider re-scores → new #1 emerges
```

---

## The scoring formula

Every hotel result gets a score from 0 to 1:

```
score = (price_score × price_weight)
      + (location_score × location_weight)
      + (rating_score × rating_weight)
      + (cancellation_score × cancellation_weight)
      + (amenities_score × amenities_weight)
```

All weights must sum to 1.0.

### How each component is scored (0 to 1)

| Component | Formula | Example |
|---|---|---|
| price_score | 1 − (price / max_budget) | €89 / €150 = 0.41 → score = 0.59 |
| location_score | 1 − (distance_km / max_distance) | 0.3km / 5km = 0.06 → score = 0.94 |
| rating_score | rating / 5.0 | 4.3 / 5.0 → score = 0.86 |
| cancellation_score | free=1.0, paid=0.3, none=0.0 | Free cancellation → 1.0 |
| amenities_score | matched / desired | Has wifi+breakfast out of 3 desired → 0.67 |

### How the Consumer Agent sets weights from what the user says

| User says | What changes |
|---|---|
| "cheapest possible" | price_weight → 0.55, reduce others |
| "best location" / "near X" | location_weight → 0.45 |
| "highest rated" | rating_weight → 0.45 |
| "I might cancel" / "need flexibility" | cancellation_weight → 0.40 |
| "I need breakfast and wifi" | amenities_weight → 0.25 |
| "don't care about X" | X_weight → 0.0, redistribute |

Default balanced weights when nothing is emphasized: price=0.25, location=0.25, rating=0.20, cancellation=0.15, amenities=0.15

---

## CRUD operations we need to demo

| Operation | What the user says | What happens |
|---|---|---|
| **Search** | "Find me a hotel in Berlin" | Consumer extracts constraints → Provider calls API → scores → returns top 3 |
| **Book** | "Book the first one" | Consumer sends book request → Provider calls API create endpoint → returns confirmation |
| **Read** | "Show my booking" | Consumer requests details → Provider calls API with booking ID → returns info |
| **Cancel** | "Cancel it" | Consumer confirms → Provider calls API cancel endpoint → returns refund status |

All four need to work in the demo.

---

## Message format between agents

### Consumer → Provider (via Orca)

```json
{
  "action": "search",
  "destination": "Berlin",
  "check_in": "2026-03-19",
  "check_out": "2026-03-21",
  "guests": 1,
  "hard_constraints": {
    "max_price_per_night": 150,
    "currency": "EUR"
  },
  "weights": {
    "price": 0.25,
    "location": 0.30,
    "rating": 0.20,
    "cancellation": 0.15,
    "amenities": 0.10
  },
  "context": {
    "preferred_area": "Alexanderplatz",
    "arrival_time": "late night"
  }
}
```

For booking:
```json
{
  "action": "book",
  "option_id": "hotel_abc123",
  "guest_name": "...",
  "check_in": "2026-03-19",
  "check_out": "2026-03-21"
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
      "id": "hotel_abc123",
      "name": "Motel One Berlin-Alexanderplatz",
      "price_per_night": 89,
      "rating": 4.3,
      "distance_km": 0.3,
      "free_cancellation": true,
      "amenities": ["wifi", "breakfast"],
      "total_score": 0.87,
      "score_breakdown": {
        "price": 0.59,
        "location": 0.94,
        "rating": 0.86,
        "cancellation": 1.0,
        "amenities": 0.67
      },
      "tag": "BEST_BALANCE"
    },
    {
      "id": "hotel_def456",
      "name": "Generator Berlin Mitte",
      "price_per_night": 62,
      "total_score": 0.81,
      "tag": "CHEAPEST"
    },
    {
      "id": "hotel_ghi789",
      "name": "Hotel Indigo Berlin",
      "price_per_night": 142,
      "total_score": 0.79,
      "tag": "HIGHEST_RATED"
    }
  ],
  "negotiation_note": "Best balance is 41% under budget and 300m walk. Cheapest drops to 3.6 rating and 1.2km. Highest rated hits near price ceiling. Free cancellation only on options 1 and 3."
}
```

The `negotiation_note` is key — it's the Provider explaining tradeoffs to the Consumer. This is what shows up in Orca's trace and impresses judges.

---

## Work split

### Person A — Consumer Agent

**You own:** Everything between the user and Orca.

Build:
- System prompt that makes the LLM extract constraints from natural language
- Weight engine: takes user phrases → outputs weight dictionary
- Response formatter: takes scored results → writes a human-friendly recommendation
- Follow-up handler: detects changed constraints → re-weights → re-sends to Provider
- Confirmation flow: asks "want me to book?" before sending book/cancel actions

Test independently with:
- Hardcoded mock responses from the Provider (use the JSON above)
- Verify: different user inputs produce different weights
- Verify: changing a constraint mid-conversation triggers a re-request

**Deliverable:** Consumer agent that registers with Orca, sends structured JSON, and handles responses.

---

### Person B — Provider Agent

**You own:** Everything between Orca and the Hotel API.

Build:
- API client: wrapper around the assigned Hotel API (search, book, cancel endpoints)
- Scoring engine: takes API results + weights → calculates scores → ranks → tags top 3
- Negotiation note generator: writes a brief explanation of tradeoffs
- CRUD handler: routes actions (search/book/read/cancel) to the right API call
- Mock data fallback: if the API is slow or down, return realistic fake results

Test independently with:
- Hardcoded requests (use the JSON above as input)
- Verify: changing weights produces different rankings
- Verify: booking and cancellation return proper confirmations

**Deliverable:** Provider agent that registers with Orca, receives structured JSON, calls the API, and returns scored results.

---

### Person C — Orca integration + demo

**You own:** Making the two agents talk to each other, and the demo.

Build:
- Orca SDK setup: register both agents, configure message routing
- End-to-end testing: send a user message → verify it flows through Consumer → Orca → Provider → back
- Simple chat interface (terminal or Streamlit — nothing fancy)
- Weather API integration (bonus points for judges)
- Demo script rehearsal

Test:
- Full flow works: search → results → re-negotiation → book → cancel
- Orca dashboard shows clean agent trace with all messages visible
- Demo runs within 3–5 minutes

**Deliverable:** Working end-to-end system + polished demo.

---

## Timeline (19:00 – 21:00)

| Time | Person A (Consumer) | Person B (Provider) | Person C (Orca + Demo) |
|---|---|---|---|
| 19:00–19:20 | Prompt engineering + weight engine | API client + mock data | Orca SDK setup from boilerplate |
| 19:20–19:45 | Parse → JSON working | Score engine working | Connect agents via Orca |
| 19:45–20:15 | Re-negotiation logic | CRUD (book + cancel) | First end-to-end test |
| 20:15–20:40 | Edge cases + polish | Edge cases + polish | Weather API bonus + full flow test |
| 20:40–21:00 | Help with demo | Help with demo | Rehearse demo script |

**Checkpoint at 19:45:** Both agents MUST be independently testable by now. If not, cut scope.

---

## Demo script (3–5 min)

### Turn 1 — Search (60s)
> **User:** "Find me a hotel in Berlin next Thursday to Saturday. Under €150 per night, near Alexanderplatz."

Show: Consumer parsing → JSON in Orca → Provider scoring → 3 results returned

> **Agent:** "Top pick: Motel One at €89/night — 300m from Alexanderplatz, rated 4.3, 41% under your budget."

### Turn 2 — Re-negotiation (60s)
> **User:** "I might cancel this trip. Need free cancellation. Also, breakfast included."

Show: weights shift in Orca → Provider re-scores → new #1

> **Agent:** "Updated recommendation: Hampton by Hilton at €112/night. Free cancellation and breakfast included. Previous pick didn't offer free cancellation."

### Turn 3 — Book (45s)
> **User:** "Book it."

Show: book request in Orca → Provider calls API → confirmation

> **Agent:** "Booked! Confirmation #HBB-4821. Free cancellation until March 18."

### Turn 4 — Cancel (30s)
> **User:** "Trip is off. Cancel."

Show: cancel in Orca → done

> **Agent:** "Cancelled. Full refund processing."

### Turn 5 — Show Orca dashboard (30s)
Open Orca. Point at the full message trace. Highlight the negotiation_note where Provider explains tradeoffs. Highlight the weight change when user asked for flexibility.

---

## Folder structure

```
travelneg/
├── consumer_agent/
│   ├── agent.py           # Person A: main agent logic
│   ├── weight_engine.py   # Person A: NL → weights
│   └── prompts.py         # Person A: system prompts
├── provider_agent/
│   ├── agent.py           # Person B: main agent logic
│   ├── api_client.py      # Person B: Hotel API wrapper
│   ├── scorer.py          # Person B: scoring formula
│   └── mock_data.py       # Person B: fallback data
├── shared/
│   ├── models.py          # Shared: Pydantic models for messages
│   └── orca_config.py     # Person C: Orca SDK setup
├── app.py                 # Person C: chat interface
├── requirements.txt
└── README.md
```

---

## What to cut if running out of time

**Priority order (cut from bottom first):**

1. Weather API integration ← cut this first
2. Read booking details (just show confirmation from the book step)
3. Cancel flow (mention "cancellation works the same way" in demo)
4. Fancy response formatting
5. ~~Search + Scoring + Re-negotiation~~ ← NEVER cut this, it's the whole point

**Minimum viable demo:** User says something → Consumer extracts constraints and weights → Provider scores results → recommendation shown → user changes mind → re-negotiation produces new ranking. That's enough to win if it works cleanly.

---

## Risk plan

| Problem | Solution |
|---|---|
| Hotel API is down or slow | Person B has mock_data.py ready. Swap in 2 minutes. |
| Orca won't connect | Person C falls back to direct function calls. Explain in demo "this would be Orca-routed." |
| LLM is rate-limited | Cache the first successful search. Demo from cache. |
| Team member gets stuck | Everyone tests independently first. Consumer works with mock Provider. Provider works with hardcoded requests. |
| Don't finish CRUD | Search + scoring + re-negotiation is the minimum. See "what to cut" above. |

---

## One-liner for the pitch

> Two AI agents negotiate hotel bookings for you — one understands what you want, the other finds the best deal. They talk to each other through Orca so you never have to fill a booking form again.
