# Project Research Summary

**Project:** Hotel Booking Provider Agent (TravelNeg)
**Domain:** API Integration + Weighted Scoring Engine for Hotel Search
**Researched:** 2025-01-20
**Confidence:** HIGH

## Executive Summary

This is a **Python API integration project with a scoring engine** — a common pattern in travel tech. The project wraps the Amadeus Hotel API to search for hotels, then applies a weighted scoring formula to rank results by user preferences (price, location, rating, cancellation policy, amenities). The "negotiation" feature is actually **re-scoring cached results with changed weights**, not new API calls — this is the core innovation that makes the demo compelling.

**Recommended approach:** Use the Amadeus Python SDK (not raw HTTP) for search operations, Pydantic v2 for all data validation, and a strict separation of concerns: `api_client.py` fetches data, `scorer.py` ranks it, `agent.py` routes requests. Build `mock_data.py` first and match its structure to real Amadeus responses exactly — this is your safety net. Booking/cancel operations must be mocked since Amadeus sandbox doesn't support them.

**Key risks:** (1) Amadeus sandbox returns synthetic data with edge cases (€0 prices, null ratings) that will break naive scoring — add defensive guards everywhere. (2) Rate limits (2,000/month free tier) can exhaust mid-demo — implement automatic mock fallback on 429 errors. (3) Mock data shape mismatches cause crashes when switching to real API — use a transformer layer and match Amadeus response structure exactly from day one.

## Key Findings

### Recommended Stack

The stack is Python 3.11+ with the Amadeus SDK for hotel search, Pydantic v2 for data validation, and pytest with respx for testing.

**Core technologies:**
- **Python 3.11+:** Modern async support, better error messages, required for Pydantic v2 performance
- **Amadeus Python SDK (12.0.0):** Official hotel search SDK with free sandbox, handles OAuth automatically, 5-minute signup
- **Pydantic v2 (2.12+):** Industry standard validation, 10x faster than v1, auto-generates JSON schema
- **pydantic-settings + python-dotenv:** Environment config for API keys

**Development tools:**
- pytest 9.0+, respx 0.22+ (HTTP mocking), ruff 0.15+ (linting)

**Why Amadeus over competitors:** Free sandbox with no partner agreement (Booking.com/Expedia require weeks of onboarding). Official Python SDK removes auth complexity. Sufficient for hackathon: 10 req/sec, 2,000 req/month.

### Expected Features

**Must have (table stakes):**
- Search API wrapper — core demo flow
- Weighted scoring engine — 5 dimensions (price, location, rating, cancellation, amenities)
- Top-3 ranking with tags (BEST_BALANCE, CHEAPEST, HIGHEST_RATED)
- Re-score without re-fetch — the "negotiation" feature
- Mock data fallback — demo must work if API is down
- JSON action routing (search/book/cancel)
- Data normalization (API data → 0-1 scores)

**Should have (competitive):**
- Negotiation note generator — explains tradeoffs between options
- Book operation — shows complete lifecycle
- Cancel operation — completes the story
- Graceful error handling (try/except → mock fallback)

**Defer (v2+):**
- Read booking (cut first if behind)
- Multiple API providers
- Database/Redis caching
- Authentication
- Async operations

### Architecture Approach

**Four-file separation of concerns:** `agent.py` (router/facade), `api_client.py` (API adapter), `scorer.py` (business logic), `mock_data.py` (fallback data), plus `shared/models.py` (Pydantic schemas).

**Major components:**
1. **agent.py** — Request routing, response formatting. Only entry point for Consumer Agent.
2. **api_client.py** — Amadeus SDK wrapper with automatic mock fallback on errors
3. **scorer.py** — Weighted scoring formula, ranking algorithm, tagging, negotiation notes
4. **mock_data.py** — Realistic Berlin hotels matching exact Amadeus response structure
5. **shared/models.py** — Pydantic models for Hotel, SearchRequest, SearchResponse, Weights

**Key patterns:** Facade (agent.py), Adapter (api_client.py), Strategy (scorer.py with configurable weights), Fail-Safe Fallback (mock_data.py)

### Critical Pitfalls

1. **Sandbox fake data breaks scoring** — Prices of €0, null ratings, missing amenities produce NaN/infinity. **Avoid:** Add defensive guards with fallback values (e.g., `price_score = 0.5` when price is 0), clamp all scores to 0-1.

2. **Mock data shape mismatch** — Your mock structure differs from Amadeus response (camelCase, nested `offers[0].price.total`). **Avoid:** Build transformer layer in api_client.py that normalizes both real and mock into internal models. Copy actual Amadeus response from docs as mock template.

3. **Rate limit exhaustion mid-demo** — 2,000/month exhausts during dev/rehearsal. **Avoid:** Track API call count, auto-switch to mock on 429, rehearse with `USE_MOCK=true`.

4. **Division by zero in scoring** — Denominators (max_budget, max_distance, desired_amenities) can be 0 or None. **Avoid:** Set sensible defaults (DEFAULT_MAX_BUDGET=500, DEFAULT_MAX_DISTANCE=10), handle empty amenities as score=1.0.

5. **Booking endpoints don't exist in sandbox** — Amadeus sandbox is search-only. **Avoid:** Mock booking entirely from start, never attempt real booking API.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation + Scoring Engine
**Rationale:** Everything depends on Pydantic models and scorer. Scoring is the intellectual core — get it right first.
**Delivers:** Working weighted scoring with defensive guards, validated data models
**Features:** shared/models.py, scorer.py with formula, data normalization
**Avoids:** Division by zero, weights not summing to 1.0, type mismatches
**Research needed:** None — Pydantic patterns are standard

### Phase 2: API Client + Mock Data
**Rationale:** Data sources can be built in parallel once models exist. Mock data provides safety net.
**Delivers:** Amadeus integration with automatic fallback, realistic test data
**Features:** api_client.py, mock_data.py, transformer layer
**Avoids:** Mock shape mismatch, rate limit exhaustion
**Research needed:** None — Amadeus SDK is well-documented

### Phase 3: Agent Router + CRUD Operations
**Rationale:** Router connects everything. Add after all components exist.
**Delivers:** Complete request handling, search/book/cancel actions, response formatting
**Features:** agent.py with action routing, caching for re-score, book/cancel (mocked)
**Avoids:** Re-fetching on weight change (use cache), API calls on re-negotiation
**Research needed:** None — standard dispatcher pattern

### Phase 4: Polish + Demo Prep
**Rationale:** Negotiation notes and error handling are judge-impressers, not core functionality.
**Delivers:** Tradeoff explanations, graceful error handling, demo reliability
**Features:** Negotiation note generator, comprehensive error boundaries
**Avoids:** Demo crashes from edge cases
**Research needed:** None — template-based generation

### Phase Ordering Rationale

- **Models first** because every component imports Pydantic schemas — can't write api_client.py or scorer.py without `Hotel`, `Weights`, `ScoredHotel` types
- **Scorer in Phase 1** (not later) because defensive scoring guards must be built from day one — retrofitting is error-prone
- **Mock data parallel with API client** because neither depends on the other, and mock is the safety net for API failures
- **Agent.py last** because it's glue code that requires all other components to exist
- **Caching in Phase 3** (not earlier) because it's only needed for re-scoring optimization, which happens after basic search works

### Research Flags

**Phases likely needing deeper research during planning:**
- None identified — this is a well-documented pattern with clear Amadeus SDK docs

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** Pydantic v2 validation is extremely well-documented
- **Phase 2:** Amadeus SDK has official Python examples
- **Phase 3:** Facade/router pattern is standard Python
- **Phase 4:** Template-based string generation is trivial

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified via PyPI, Amadeus SDK is official |
| Features | HIGH | Project README defines exact contract and priorities |
| Architecture | HIGH | Standard patterns for API integration + scoring |
| Pitfalls | MEDIUM-HIGH | Based on Amadeus docs + common API integration issues |

**Overall confidence:** HIGH

### Gaps to Address

- **Exact Amadeus response fields** — Research identified field structure but exact mapping of amenities and cancellation policies needs verification against live sandbox response
- **Distance calculation** — Amadeus may not return distance; may need haversine calculation from coordinates
- **City code mapping** — User says "Berlin", Amadeus needs "BER" — need lookup table or use multi-city search

## Sources

### Primary (HIGH confidence)
- PyPI package pages (verified 2025-01-14): pydantic 2.12.5, httpx 0.28.1, amadeus 12.0.0, pytest 9.0.2
- Amadeus Self-Service Documentation — https://developers.amadeus.com
- Project README.MD — scoring formula, message formats, demo script, cut priorities

### Secondary (MEDIUM confidence)
- Amadeus Python SDK GitHub — https://github.com/amadeus4dev/amadeus-python
- Common hotel API integration patterns from travel tech domain

### Tertiary (LOW confidence)
- Specific Amadeus response field mappings — need validation against live sandbox

---
*Research completed: 2025-01-20*
*Ready for roadmap: yes*
