# Requirements: TravelNeg Provider Agent

**Defined:** 2026-03-18
**Core Value:** Given weighted preferences, score hotel results accurately and return ranked options with clear tradeoff explanations

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Search & Scoring

- [ ] **SRCH-01**: Provider Agent calls Amadeus API with destination, dates, guests, and max price constraints
- [ ] **SRCH-02**: API response is normalized to 0–1 scores across 5 dimensions (price, location, rating, cancellation, amenities)
- [ ] **SRCH-03**: Scoring engine applies weighted formula — all weights sum to 1.0, produces total score 0–1
- [ ] **SRCH-04**: Results ranked by total score, top 3 returned with score breakdowns
- [ ] **SRCH-05**: Top results tagged: BEST_BALANCE, CHEAPEST, HIGHEST_RATED
- [ ] **SRCH-06**: Re-scoring with changed weights produces new rankings without re-fetching from API

### Negotiation

- [ ] **NEGO-01**: Negotiation note generator explains tradeoffs between top 3 options (price vs location vs rating)

### CRUD

- [ ] **CRUD-01**: JSON action router dispatches search/book/read/cancel to correct handler
- [ ] **CRUD-02**: Book operation sends booking request and returns confirmation ID
- [ ] **CRUD-03**: Read operation fetches booking details by booking ID
- [ ] **CRUD-04**: Cancel operation cancels booking and returns refund status

### Reliability

- [ ] **RLBL-01**: Mock data fallback (mock_data.py) returns realistic Berlin hotel results when API is unavailable
- [ ] **RLBL-02**: Graceful error handling auto-falls back to mock data on API failure

### Data Models

- [ ] **DATA-01**: Pydantic models in shared/models.py match README JSON schemas exactly (Consumer→Provider and Provider→Consumer)
- [ ] **DATA-02**: Defensive scoring handles edge cases (€0 prices, null ratings, missing amenities, division by zero)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Multi-Provider

- **MPRO-01**: Support multiple hotel API providers (Booking.com, Expedia)
- **MPRO-02**: Normalize responses from different providers into common format

### Performance

- **PERF-01**: Redis/persistent caching for search results
- **PERF-02**: Async API calls for concurrent searches
- **PERF-03**: Rate limiting with exponential backoff

### Integration

- **INTG-01**: HTTP REST endpoints wrapping function interface
- **INTG-02**: OpenAPI spec for Provider Agent endpoints

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Consumer Agent | Separate person/workstream (Person A) |
| Orca SDK integration | Person C's responsibility, added later |
| Chat interface / UI | Person C's scope |
| Weather API bonus | Person C's scope |
| Authentication/sessions | Not needed for hackathon demo |
| Real-time availability checks | Sandbox doesn't reflect real inventory |
| Price negotiation/bidding | APIs don't support this; scoring IS the negotiation |
| Pagination | Amadeus returns manageable sets; we show top 3 |
| Logging infrastructure | print() sufficient for demo |
| Unit test suite | 2-hour window; manual testing with hardcoded requests |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| SRCH-01 | Phase 2 | Pending |
| SRCH-02 | Phase 1 | Pending |
| SRCH-03 | Phase 1 | Pending |
| SRCH-04 | Phase 3 | Pending |
| SRCH-05 | Phase 3 | Pending |
| SRCH-06 | Phase 3 | Pending |
| NEGO-01 | Phase 5 | Pending |
| CRUD-01 | Phase 4 | Pending |
| CRUD-02 | Phase 4 | Pending |
| CRUD-03 | Phase 4 | Pending |
| CRUD-04 | Phase 4 | Pending |
| RLBL-01 | Phase 2 | Pending |
| RLBL-02 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16 ✓
- Unmapped: 0

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-18 after initial definition*
