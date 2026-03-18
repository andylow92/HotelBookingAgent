# Roadmap: TravelNeg Provider Agent

## Overview

Build the Provider Agent for TravelNeg — a Python component that wraps the Amadeus Hotel API, scores results with weighted preferences, handles bookings, and generates negotiation notes. The journey starts with foundational data models and the scoring engine, adds API integration with mock fallback, enables complete search with ranking, implements CRUD operations, and finishes with negotiation note generation for the demo.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Data Models & Scoring Engine** - Pydantic schemas and weighted scoring formula with defensive guards
- [ ] **Phase 2: API Client & Mock Fallback** - Amadeus integration with automatic fallback to mock data
- [ ] **Phase 3: Search & Ranking** - Top 3 results with score breakdowns, tags, and re-scoring
- [ ] **Phase 4: CRUD & Action Routing** - JSON router dispatching search/book/read/cancel operations
- [ ] **Phase 5: Negotiation Notes** - Tradeoff explanations between top options

## Phase Details

### Phase 1: Data Models & Scoring Engine
**Goal**: Working weighted scoring with validated data models and defensive guards
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, SRCH-02, SRCH-03
**Success Criteria** (what must be TRUE):
  1. Pydantic models in shared/models.py validate against README JSON schemas
  2. Raw hotel data normalizes to 0–1 scores across all 5 dimensions (price, location, rating, cancellation, amenities)
  3. Scoring engine applies weighted formula where weights sum to 1.0 and produces total score 0–1
  4. Edge cases (€0 prices, null ratings, missing amenities, division by zero) produce valid scores, not crashes
**Plans**: 1 plan

Plans:
- [ ] 01-01-PLAN.md — Pydantic models + defensive scoring engine

### Phase 2: API Client & Mock Fallback
**Goal**: Data fetching layer that always returns hotel results, even when API is down
**Depends on**: Phase 1
**Requirements**: SRCH-01, RLBL-01, RLBL-02
**Success Criteria** (what must be TRUE):
  1. api_client.py calls Amadeus API with destination, dates, guests, and max price
  2. mock_data.py returns realistic Berlin hotel results matching Amadeus response structure
  3. API failures (429, timeout, errors) automatically fall back to mock data without crashing
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: Search & Ranking
**Goal**: Complete search returns top 3 scored, tagged results with re-score capability
**Depends on**: Phase 2
**Requirements**: SRCH-04, SRCH-05, SRCH-06
**Success Criteria** (what must be TRUE):
  1. Search returns top 3 results ranked by total score with individual dimension breakdowns
  2. Results are tagged: BEST_BALANCE (highest total), CHEAPEST (best price score), HIGHEST_RATED (best rating score)
  3. Changing weights produces new rankings from cached results without re-fetching from API
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: CRUD & Action Routing
**Goal**: Agent routes all actions and handles complete booking lifecycle
**Depends on**: Phase 3
**Requirements**: CRUD-01, CRUD-02, CRUD-03, CRUD-04
**Success Criteria** (what must be TRUE):
  1. agent.py receives JSON action (search/book/read/cancel) and dispatches to correct handler
  2. Book operation accepts hotel selection and returns confirmation ID
  3. Read operation fetches booking details by ID
  4. Cancel operation cancels booking and returns refund status
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: Negotiation Notes
**Goal**: Tradeoff explanations that make the demo compelling
**Depends on**: Phase 4
**Requirements**: NEGO-01
**Success Criteria** (what must be TRUE):
  1. Negotiation note generator produces human-readable explanation of tradeoffs between top 3 options
  2. Notes explain price vs location vs rating tradeoffs specific to the actual results
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Models & Scoring Engine | 0/1 | Planned | - |
| 2. API Client & Mock Fallback | 0/TBD | Not started | - |
| 3. Search & Ranking | 0/TBD | Not started | - |
| 4. CRUD & Action Routing | 0/TBD | Not started | - |
| 5. Negotiation Notes | 0/TBD | Not started | - |

---
*Roadmap created: 2026-03-18*
*Last updated: 2026-03-18*
