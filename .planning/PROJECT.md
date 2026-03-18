# TravelNeg — Provider Agent

## What This Is

The Provider Agent for TravelNeg, a hotel booking negotiator system where two AI agents collaborate via Orca (Lexia). This component handles everything between Orca and the Hotel API: searching for hotels, scoring results with weighted preferences, handling bookings and cancellations, and generating negotiation notes that explain tradeoffs. Built in Python (1,043 LOC), it receives structured JSON from the Consumer Agent and returns scored, ranked results with travel-advisor-tone explanations.

## Core Value

Given a set of weighted preferences from the Consumer Agent, the Provider Agent must score hotel results accurately and return ranked options with clear tradeoff explanations — this is the intelligence that powers the negotiation loop.

## Requirements

### Validated

- ✓ Provider Agent wraps Amadeus sandbox Hotel API for search, book, read, and cancel — v1.0
- ✓ Scoring engine implements weighted formula: price, location, rating, cancellation, amenities (all 0–1, weights sum to 1.0) — v1.0
- ✓ Search returns top 3 scored results with score breakdowns and tags (BEST_BALANCE, CHEAPEST, HIGHEST_RATED) — v1.0
- ✓ Negotiation note generator explains tradeoffs between top options with concrete numbers — v1.0
- ✓ CRUD handler routes actions (search/book/read/cancel) to correct handler — v1.0
- ✓ Mock data fallback returns realistic Berlin hotel results when API is down — v1.0
- ✓ JSON in/out interface matches README message formats exactly — v1.0
- ✓ Follows README folder structure: provider_agent/ with agent.py, api_client.py, scorer.py, mock_data.py — v1.0
- ✓ Shared models (Pydantic) in shared/models.py match README JSON schemas — v1.0
- ✓ Re-scoring works: changed weights produce different rankings without re-fetching — v1.0

### Active

(None — v1.0 complete. Next milestone TBD.)

### Out of Scope

- Consumer Agent — separate person/workstream
- Orca SDK integration — Person C adds this
- Chat interface / UI — Person C's responsibility
- Weather API bonus feature — Person C's scope
- HTTP/REST endpoints — functions only, Orca wraps them
- Authentication/user management — not needed for hackathon demo

## Context

- **v1.0 shipped** — Full Provider Agent with search, scoring, CRUD, and negotiation notes
- **Tech stack:** Python 3.13, Pydantic v2, Amadeus SDK, 1,043 LOC across 8 files
- **Architecture:** `handle_action()` entry point → dispatch dict → handlers → scorer/api_client
- **Hackathon project** — built for 3–5 minute demo
- **Team of 3** — Person A (Consumer Agent), Person B (Provider Agent), Person C (Orca + Demo)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Amadeus sandbox as primary Hotel API | Free, realistic data, SDK handles OAuth2 | ✓ Good — works for demo, sandbox data incomplete but mock fallback covers gaps |
| Mock data fallback on any error | Demo must work even if API is down | ✓ Good — instant fallback, 7 realistic Berlin hotels |
| JSON functions, not HTTP endpoints | Orca wraps functions directly | ✓ Good — clean interface, no server overhead |
| In-memory booking store | Hackathon demo only, resets on restart | ✓ Good — simple, no database dependency |
| Dispatch dict pattern for routing | Clean, extensible, no if/elif chains | ✓ Good — easy to add new actions |
| Travel-advisor tone for negotiation notes | Makes demo compelling for judges | ✓ Good — concrete numbers, warm professional tone |

## Constraints

- **Language**: Python — required for Orca (Lexia) integration
- **API Cost**: Free/sandbox hotel API only
- **Interface**: JSON in/out functions, not HTTP endpoints
- **Schema**: Must match README message formats (Consumer ↔ Provider JSON)
- **Structure**: provider_agent/, shared/ folder structure
- **Fallback**: mock_data.py for API unavailability

---
*Last updated: 2026-03-18 after v1.0 milestone*
