# Phase 03: Search & Ranking — Research

**Researched:** 2026-03-18
**Question:** What do I need to know to PLAN this phase well?

## Critical Discovery: Most Logic Already Exists

**The scoring, ranking, top-3 selection, and tagging are fully implemented in Phase 1's `scorer.py`.** The function `score_and_rank()` (line 194–239) already:
- Scores all hotels against user weights
- Sorts by `total_score` descending
- Slices to top 3
- Assigns BEST_BALANCE, CHEAPEST, HIGHEST_RATED tags via `_assign_tags()`

**This phase is a composition/wiring task, not an algorithm task.** The work is:
1. A `search()` function that pipes `api_client.search_hotels()` → `scorer.score_and_rank()` → `SearchResponse`
2. A `rescore()` function that pipes cached raw hotels + new weights → `scorer.score_and_rank()` → `SearchResponse`

## Existing Interfaces (What We Wire Together)

### Input: `api_client.search_hotels()`
```python
def search_hotels(
    destination: str, check_in: date, check_out: date,
    guests: int, max_price: float = 500.0
) -> tuple[list[dict], bool]:  # (hotels, is_mock)
```
- Returns flat hotel dicts matching scorer's expected format
- Never raises — always returns data (real or mock)
- `is_mock` flag distinguishes data source

### Processing: `scorer.score_and_rank()`
```python
def score_and_rank(
    hotels: list[dict], weights: Weights,
    max_budget: float, desired_amenities: list[str] | None = None
) -> list[HotelOption]:  # top 3, tagged
```
- Accepts raw hotel dicts (same format api_client returns)
- Returns `list[HotelOption]` — already scored, ranked, top-3, tagged
- Tags assigned: #1 → BEST_BALANCE, cheapest remaining → CHEAPEST, highest rated remaining → HIGHEST_RATED

### Output: `SearchResponse` model
```python
class SearchResponse(BaseModel):
    action: Literal["search_results"]
    options: list[HotelOption] = Field(default_factory=list)
    negotiation_note: str = ""  # Phase 5, leave empty
```

### Trigger: `SearchRequest` model
```python
class SearchRequest(BaseModel):
    action: Literal["search"]
    destination: str
    check_in: date
    check_out: date
    guests: int = Field(ge=1, default=1)
    hard_constraints: HardConstraints  # has max_price_per_night, currency
    weights: Weights = Field(default_factory=Weights)
    context: SearchContext = Field(default_factory=SearchContext)  # has desired_amenities
```

## Requirement → Implementation Mapping

### SRCH-04: Results ranked by total score, top 3 returned with score breakdowns
- **Already done by** `scorer.score_and_rank()` — sorts descending, slices [:3]
- **Score breakdowns** already in each `HotelOption.score_breakdown` (ScoreBreakdown model)
- **Phase 3 work:** Wire it into a `search()` function that accepts `SearchRequest` and returns `SearchResponse`

### SRCH-05: Top results tagged BEST_BALANCE, CHEAPEST, HIGHEST_RATED
- **Already done by** `scorer._assign_tags()` — called inside `score_and_rank()`
- **Phase 3 work:** None beyond calling `score_and_rank()` — tags are assigned automatically

### SRCH-06: Re-scoring with changed weights without re-fetching from API
- **Needs new code:** A `rescore()` function
- **Per 03-CONTEXT.md decisions:**
  - Separate function from `search()` — not a mode flag
  - Caller holds cache — raw hotels passed explicitly (no module-level state)
  - Tags re-assigned based on new rankings (automatic — `score_and_rank()` always re-tags)
  - Returns same `SearchResponse` format as `search()`

## Design for `search()` and `rescore()`

### `search(request: SearchRequest) -> tuple[SearchResponse, list[dict]]`
Pipeline:
1. Extract params from `SearchRequest` (destination, dates, guests, max_price)
2. Call `api_client.search_hotels(...)` → `(raw_hotels, is_mock)`
3. Call `scorer.score_and_rank(raw_hotels, request.weights, max_budget, desired_amenities)` → `list[HotelOption]`
4. Wrap in `SearchResponse(action="search_results", options=ranked)`
5. Return `(SearchResponse, raw_hotels)` — raw hotels for caller to cache

**Why return tuple:** Per context decision, caller holds the cache. Returning raw hotels alongside the response gives the caller what they need for future `rescore()` calls without a separate API fetch.

### `rescore(raw_hotels: list[dict], weights: Weights, max_budget: float, desired_amenities: list[str] | None = None) -> SearchResponse`
Pipeline:
1. Call `scorer.score_and_rank(raw_hotels, weights, max_budget, desired_amenities)` → `list[HotelOption]`
2. Wrap in `SearchResponse(action="search_results", options=ranked)`
3. Return the response

**Key insight:** `rescore()` is literally `score_and_rank()` + wrap in `SearchResponse`. Trivial but important to have as a named function matching the domain concept.

## File Placement

New file: **`provider_agent/search.py`**
- Follows existing pattern: `provider_agent/` contains all provider logic
- Imports from `provider_agent.api_client` and `provider_agent.scorer`
- Imports models from `shared.models`

## Edge Cases & Error Handling

| Case | Handling |
|------|----------|
| API returns 0 hotels | `api_client.search_hotels()` already falls back to mock — never returns empty |
| All hotels score identically | `score_and_rank()` returns first 3; tags still assigned (BEST_BALANCE to #1, etc.) |
| Fewer than 3 hotels | `_assign_tags()` handles 1 or 2 results gracefully (checks `len(options)`) |
| Empty raw_hotels to rescore | `score_and_rank()` returns `[]`; `SearchResponse.options` defaults to `[]` |
| Weights all zero | `Weights` model auto-normalizes to equal (0.2 each) — handled at model layer |

## What This Phase Does NOT Do

- **No negotiation notes** — `SearchResponse.negotiation_note` stays `""` (Phase 5: NEGO-01)
- **No action routing** — Phase 4 handles dispatching to search/book/read/cancel
- **No caching infrastructure** — caller holds cache; no Redis, no module state
- **No new models** — all needed Pydantic models exist in `shared/models.py`

## Complexity Assessment

**Low complexity.** This is a thin composition layer:
- `search()`: ~10 lines of wiring (extract params → api_client → scorer → wrap)
- `rescore()`: ~5 lines (scorer → wrap)
- No new algorithms, no new models, no new external dependencies

## Dependencies

- `provider_agent.api_client.search_hotels` (Phase 2 — complete ✓)
- `provider_agent.scorer.score_and_rank` (Phase 1 — complete ✓)
- `shared.models` (Phase 1 — complete ✓, all models exist)

---

*Research complete. Phase is ready for planning.*
*Key insight: This is a wiring/composition phase — most logic already exists in scorer.py.*
