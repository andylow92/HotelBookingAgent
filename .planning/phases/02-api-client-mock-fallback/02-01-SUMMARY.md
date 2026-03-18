---
phase: 02-api-client-mock-fallback
plan: 01
subsystem: api
tags: [amadeus, hotel-search, mock-data, fallback, sdk]

# Dependency graph
requires:
  - phase: 01-data-models-scoring-engine
    provides: "scorer.py (score_hotel, score_and_rank) and models.py (Weights, HotelOption, ScoreBreakdown)"
provides:
  - "search_hotels() — public API returning (hotels, is_mock) tuple"
  - "get_mock_hotels() — 7 static Berlin hotel dicts for fallback"
  - "Amadeus v3 two-step flow (Hotel List → Hotel Offers Search)"
  - "Automatic mock fallback on missing credentials or API errors"
affects: [provider-agent-tool, a2a-integration, consumer-agent]

# Tech tracking
tech-stack:
  added: [amadeus-sdk-v12]
  patterns: [try-except-fallback, two-step-api-flow, is_mock-flag]

key-files:
  created:
    - provider_agent/mock_data.py
    - provider_agent/api_client.py
  modified: []

key-decisions:
  - "Broad except Exception catch — all API errors trigger mock fallback, no error type distinction"
  - "No retry logic — single failure triggers immediate fallback (locked decision)"
  - "distance_km=0.0 and amenities=[] for API results — Amadeus offers endpoint doesn't provide them, scorer handles with neutral scores"

patterns-established:
  - "Fallback pattern: try real API → catch any error → return mock data with is_mock=True"
  - "City code resolution: dict lookup with uppercase[:3] heuristic fallback"

requirements-completed: [SRCH-01, RLBL-01, RLBL-02]

# Metrics
duration: 2min
completed: 2026-03-18
---

# Phase 2 Plan 1: API Client & Mock Fallback Summary

**Amadeus Hotel Search v3 client with automatic mock-data fallback — search_hotels() always returns data, never raises**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-18T12:32:28Z
- **Completed:** 2026-03-18T12:34:17Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments
- Created 7 realistic Berlin mock hotels with varied profiles for demo scoring differentiation
- Built two-step Amadeus v3 API client (Hotel List → Hotel Offers Search) with response normalization
- Implemented automatic fallback: missing credentials or any API error → mock data with is_mock=True flag
- Verified full integration chain: search_hotels() → score_and_rank() → tagged top 3 results

## Task Commits

Each task was committed atomically:

1. **Task 1: Create mock_data.py with realistic Berlin hotel data** - `940d036` (feat)
2. **Task 2: Create api_client.py with Amadeus integration and fallback** - `6d144de` (feat)

## Files Created/Modified
- `provider_agent/mock_data.py` — 7 static Berlin hotels with budget/mid-range/premium profiles; get_mock_hotels() export
- `provider_agent/api_client.py` — search_hotels() public API, _get_client(), _call_amadeus(), _normalize_response() helpers; amadeus SDK integration

## Decisions Made
- Used broad `except Exception` for fallback trigger — per locked decision, no distinction between error types
- Set `distance_km=0.0` and `amenities=[]` for real API results since Amadeus offers endpoint doesn't provide them; scorer handles these with neutral 0.5 scores
- City code resolution uses dict lookup for known cities + `destination.upper()[:3]` heuristic for unknown ones
- Installed amadeus SDK v12.0.0 in .venv

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

**External services require manual configuration.** Amadeus API credentials needed for real hotel search:
- `AMADEUS_CLIENT_ID` — from https://developers.amadeus.com → My Self-Service Workspace → API keys
- `AMADEUS_CLIENT_SECRET` — same page as AMADEUS_CLIENT_ID
- Without these, the system uses mock data automatically (fully functional for demos)

## Next Phase Readiness
- `search_hotels()` is ready for consumption by provider agent tool
- Mock fallback ensures demo always works even without API credentials
- Output dicts are verified compatible with `scorer.score_and_rank()` from Phase 1
- Next: wire into A2A provider agent as a tool

## Self-Check: PASSED

- [x] provider_agent/mock_data.py exists
- [x] provider_agent/api_client.py exists
- [x] 02-01-SUMMARY.md exists
- [x] Commit 940d036 found (Task 1)
- [x] Commit 6d144de found (Task 2)

---
*Phase: 02-api-client-mock-fallback*
*Completed: 2026-03-18*
