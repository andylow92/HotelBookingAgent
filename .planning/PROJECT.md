# TravelNeg — Provider Agent

## What This Is

The Provider Agent for TravelNeg, a hotel booking negotiator system where two AI agents collaborate via Orca (Lexia). This component handles everything between Orca and the Hotel API: searching for hotels, scoring results with weighted preferences, handling bookings and cancellations, and generating negotiation notes that explain tradeoffs. Built in Python, it receives structured JSON from the Consumer Agent and returns scored, ranked results.

## Core Value

Given a set of weighted preferences from the Consumer Agent, the Provider Agent must score hotel results accurately and return ranked options with clear tradeoff explanations — this is the intelligence that powers the negotiation loop.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Provider Agent wraps a free external Hotel API (e.g., Amadeus sandbox) for search, book, read, and cancel
- [ ] Scoring engine implements the weighted formula: price, location, rating, cancellation, amenities (all 0–1, weights sum to 1.0)
- [ ] Search returns top 3 scored results with score breakdowns and tags (BEST_BALANCE, CHEAPEST, HIGHEST_RATED)
- [ ] Negotiation note generator explains tradeoffs between top options
- [ ] CRUD handler routes actions (search/book/read/cancel) to the right API call
- [ ] Mock data fallback (mock_data.py) returns realistic results when API is down
- [ ] JSON in/out interface matches the README message formats exactly
- [ ] Follows README folder structure: provider_agent/ with agent.py, api_client.py, scorer.py, mock_data.py
- [ ] Shared models (Pydantic) in shared/models.py match README JSON schemas
- [ ] Re-scoring works: changed weights produce different rankings without re-fetching

### Out of Scope

- Consumer Agent — separate person/workstream, not part of this build
- Orca SDK integration — will be added later by Person C
- Chat interface / UI — Person C's responsibility
- Weather API bonus feature — Person C's scope
- HTTP/REST endpoints — functions only, Orca wraps them later
- Authentication/user management — not needed for hackathon demo

## Context

- **Hackathon project** — 2-hour build window, needs to work for a 3–5 minute demo
- **Team of 3** — Person A (Consumer Agent), Person B (Provider Agent, this project), Person C (Orca + Demo)
- **Orca (Lexia)** — multi-agent orchestration platform; agents register and exchange JSON messages
- **Integration point** — Provider Agent will be called by Orca with Consumer Agent's JSON payloads
- **Demo flow** — search → results → re-negotiation (weight change) → book → cancel
- **The scoring formula and message formats in the README are the contract** between Consumer and Provider agents

## Constraints

- **Language**: Python — required for Orca (Lexia) integration
- **API Cost**: Must use a free/sandbox hotel API (hackathon, no budget)
- **Interface**: JSON in/out functions, not HTTP endpoints
- **Schema**: Must match README message formats exactly (Consumer ↔ Provider JSON)
- **Structure**: Must follow README folder structure (provider_agent/, shared/)
- **Fallback**: Must have mock_data.py for when external API is unreachable

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Free external Hotel API (e.g., Amadeus sandbox) as primary | Hackathon has no budget; need real-looking data | — Pending |
| Mock data fallback | Demo must work even if API is down | — Pending |
| JSON functions, not HTTP endpoints | Orca integration wraps functions directly; endpoints are unnecessary overhead | — Pending |
| Follow README structure exactly | Team contract — Consumer Agent and Orca integration depend on these interfaces | — Pending |

---
*Last updated: 2026-03-18 after initialization*
