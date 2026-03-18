---
phase: 05-negotiation-notes
plan: 01
subsystem: api
tags: [scoring, negotiation, tradeoffs, travel-advisor]

# Dependency graph
requires:
  - phase: 01-scoring-engine
    provides: score_and_rank(), HotelOption with tags, ScoreBreakdown
  - phase: 03-search-rescore
    provides: search() and rescore() functions returning SearchResponse
provides:
  - generate_negotiation_note() function in scorer.py
  - Populated negotiation_note field in all SearchResponse outputs
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [tag-based role identification, adaptive-length note generation, weight-aware emphasis]

key-files:
  created: []
  modified: [provider_agent/scorer.py, provider_agent/search.py]

key-decisions:
  - "generate_negotiation_note lives in scorer.py (adjacent to ranking logic, no new file)"
  - "Pure f-string composition — no templates library, no LLM call, fully deterministic"
  - "Adaptive length: short note when score spread < 0.05, full comparison otherwise"
  - "Handle negative price diffs gracefully when BEST_BALANCE is cheapest overall"

patterns-established:
  - "Tag-based role lookup: {o.tag: o for o in options if o.tag} for safe role identification"
  - "Directional comparison: check sign of diffs before phrasing (cheaper vs more, drops vs rated higher)"

requirements-completed: [NEGO-01]

# Metrics
duration: 3min
completed: 2026-03-18
---

# Phase 5 Plan 1: Negotiation Notes Summary

**Deterministic travel-advisor tradeoff notes comparing BEST_BALANCE, CHEAPEST, and HIGHEST_RATED hotels with concrete € prices, star ratings, and km distances**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-18T14:21:30Z
- **Completed:** 2026-03-18T14:24:27Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `generate_negotiation_note()` function producing warm, professional travel-advisor tradeoff explanations
- Both `search()` and `rescore()` now populate `SearchResponse.negotiation_note` with non-empty notes
- Adaptive note length: short note for closely-matched options, full comparison for divergent scores
- Edge cases handled: 0 options (empty string), 1 option (brief note), 2 options (partial comparison)
- Weight-aware emphasis: reorders comparisons based on user's dominant preference dimension

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement generate_negotiation_note() in scorer.py** - `0ed16cb` (feat)
2. **Task 2: Wire negotiation note into search() and rescore()** - `4059bcc` (feat)

## Files Created/Modified
- `provider_agent/scorer.py` - Added `generate_negotiation_note()` function (~100 lines) with guard clauses, tag-based role identification, dominant weight detection, and f-string composition
- `provider_agent/search.py` - Updated import to include `generate_negotiation_note`, wired into both `search()` and `rescore()` response construction

## Decisions Made
- `generate_negotiation_note` placed in `scorer.py` (adjacent to ranking logic, avoids new file for ~100 lines)
- Pure f-string composition — no template library, no LLM call, fully deterministic output
- Adaptive length threshold: score spread < 0.05 triggers short "closely matched" note
- Tag-based role lookup via dict comprehension for safe identification regardless of index

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed negative price diff when BEST_BALANCE is cheapest overall**
- **Found during:** Task 2 (wiring verification with mock data)
- **Issue:** When BEST_BALANCE hotel was the cheapest overall, the CHEAPEST-tagged hotel (second cheapest) showed "€-26/night cheaper" — negative price in note
- **Fix:** Added sign check: positive diff → "€X/night cheaper", negative diff → "€X/night more", near-zero → "similarly priced"
- **Files modified:** provider_agent/scorer.py
- **Verification:** Tested with budget 150 and 300 — no negative prices in notes
- **Committed in:** 4059bcc (Task 2 commit)

**2. [Rule 1 - Bug] Fixed incorrect "drops to" phrasing when cheapest has higher rating**
- **Found during:** Task 2 (wiring verification with mock data)
- **Issue:** When CHEAPEST-tagged hotel had a higher rating than BEST_BALANCE, note said "drops to 4.4 stars" (4.4 > 4.1 is not a drop)
- **Fix:** Added directional check: positive diff → "drops to X stars", negative diff → "rated higher at X stars"
- **Files modified:** provider_agent/scorer.py
- **Verification:** Tested with mock data — phrasing now correctly reflects direction
- **Committed in:** 4059bcc (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correct natural-language phrasing. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Negotiation notes complete — every SearchResponse now contains a populated `negotiation_note` field
- No remaining phases in the milestone roadmap

---
*Phase: 05-negotiation-notes*
*Completed: 2026-03-18*

## Self-Check: PASSED

All files exist, all commits verified, function present in both scorer.py and search.py.
