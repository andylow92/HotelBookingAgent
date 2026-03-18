# Phase 3: Search & Ranking - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete search pipeline that wires api_client (Phase 2) + scorer (Phase 1) together. Returns top 3 scored, tagged results as a SearchResponse. Supports re-scoring with changed weights without re-fetching from the API. Action routing and CRUD are Phase 4 — this phase only handles search and re-score.

</domain>

<decisions>
## Implementation Decisions

### Re-scoring behavior
- Separate `rescore()` function distinct from `search()` — search fetches + scores, rescore takes cached results + new weights
- Caller holds the cache in-memory — raw hotel data passed explicitly to rescore(), no module-level cache
- Tags (BEST_BALANCE, CHEAPEST, HIGHEST_RATED) re-assigned based on new rankings after re-score
- Both search() and rescore() return the same SearchResponse format — identical output structure

### Claude's Discretion
- Search function interface design — how search() composes api_client.search_hotels() + scorer.score_and_rank()
- Result presentation — how score breakdowns are surfaced in the response
- Error handling within the search pipeline
- Whether search() returns the raw hotels alongside SearchResponse for caching convenience

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The key contract: search returns SearchResponse with top 3 tagged HotelOptions, and rescore produces identical output from cached data + new weights.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-search-ranking*
*Context gathered: 2026-03-18*
