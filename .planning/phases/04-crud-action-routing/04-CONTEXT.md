# Phase 4: CRUD & Action Routing - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

JSON action router in agent.py that receives structured actions (search/book/read/cancel) and dispatches to the correct handler. Includes booking lifecycle operations backed by in-memory storage. Negotiation notes are Phase 5 — this phase handles routing and CRUD only.

</domain>

<decisions>
## Implementation Decisions

### Booking storage
- In-memory dict — `{booking_id: details}` map, resets on restart, sufficient for demo
- Mock mode fully simulates all operations — generates fake booking IDs, book/read/cancel all work without API
- Cancel refund status depends on the hotel's `free_cancellation` field (not always refundable)
- Full booking record stored: hotel name, price, dates, guest name, confirmation ID, booking status

### Claude's Discretion
- Router interface design — whether agent.py takes JSON string or dict, single `handle()` entry or per-action
- Error response format — what caller gets on invalid action, missing booking ID, failed operations
- Booking ID generation strategy (UUID, sequential, etc.)
- How search action integrates with Phase 3's `search()` and `rescore()`

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The key contract: agent.py is the single entry point that Orca calls with JSON payloads matching README message formats.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-crud-action-routing*
*Context gathered: 2026-03-18*
