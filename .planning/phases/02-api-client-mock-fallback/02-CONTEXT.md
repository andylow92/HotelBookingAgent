# Phase 2: API Client & Mock Fallback - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Data fetching layer that always returns hotel results, even when the Amadeus API is down. Includes api_client.py (Amadeus integration) and mock_data.py (fallback data). Scoring and ranking are Phase 1 (done) and Phase 3 — this phase only fetches raw hotel data.

</domain>

<decisions>
## Implementation Decisions

### Fallback trigger policy
- Fail once, fall back immediately — no retries on any error
- 5-second request timeout before treating as failure
- Missing API credentials (no key/secret set) → skip API call entirely, go straight to mock data
- All error types trigger fallback: 4xx, 5xx, timeouts, connection errors
- No distinction between "API is down" vs "bad request" — for a demo, always prefer returning results over surfacing errors

### Claude's Discretion
- Mock data realism — how many hotels, static vs randomized, level of detail
- API credential handling — env vars, config file, or other approach
- Whether the caller is informed it received mock data (silent vs flagged fallback)
- Amadeus API endpoint selection and query parameter mapping
- Response parsing and normalization to match Phase 1 data models

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Priority is reliability for a live demo: the system must always return hotel data regardless of API state.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-api-client-mock-fallback*
*Context gathered: 2026-03-18*
