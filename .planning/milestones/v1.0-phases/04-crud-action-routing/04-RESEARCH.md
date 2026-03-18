# Phase 4: CRUD & Action Routing - Research

**Researched:** 2026-03-18
**Domain:** Action routing / in-memory CRUD / Python dispatch patterns
**Confidence:** HIGH

## Summary

Phase 4 creates `provider_agent/agent.py` — the single entry point that Orca calls with JSON payloads. It receives a dict with an `"action"` field (`search`, `book`, `read`, `cancel`) and dispatches to the correct handler. Search delegates to the existing Phase 3 `search()` pipeline. Book, read, and cancel are fully mocked with an in-memory `dict` since the Amadeus sandbox is search-only (locked decision from project init).

The implementation is straightforward Python — no new dependencies needed. All request/response models already exist in `shared/models.py` (SearchRequest, BookRequest, ReadRequest, CancelRequest). The main design work is the router structure, error handling, booking ID generation, and response format for CRUD operations.

**Primary recommendation:** Single `handle_action(payload: dict) -> dict` entry point with a dispatch dict mapping action strings to handler functions. Keep all booking state in a module-level `_bookings` dict. Use `uuid4` short prefixes for booking IDs.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- In-memory dict — `{booking_id: details}` map, resets on restart, sufficient for demo
- Mock mode fully simulates all operations — generates fake booking IDs, book/read/cancel all work without API
- Cancel refund status depends on the hotel's `free_cancellation` field (not always refundable)
- Full booking record stored: hotel name, price, dates, guest name, confirmation ID, booking status

### Claude's Discretion
- Router interface design — whether agent.py takes JSON string or dict, single `handle()` entry or per-action
- Error response format — what caller gets on invalid action, missing booking ID, failed operations
- Booking ID generation strategy (UUID, sequential, etc.)
- How search action integrates with Phase 3's `search()` and `rescore()`

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CRUD-01 | JSON action router dispatches search/book/read/cancel to correct handler | Dispatch dict pattern maps `action` string → handler function in `handle_action()` |
| CRUD-02 | Book operation sends booking request and returns confirmation ID | `_handle_book()` validates option_id against last search results, stores in `_bookings` dict, returns UUID-based confirmation ID |
| CRUD-03 | Read operation fetches booking details by booking ID | `_handle_read()` looks up `_bookings[booking_id]`, returns full record or error |
| CRUD-04 | Cancel operation cancels booking and returns refund status | `_handle_cancel()` sets booking status to "cancelled", derives refund status from `free_cancellation` field |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `uuid` | 3.x | Booking ID generation | Built-in, no dependencies, `uuid4().hex[:8]` gives unique short IDs |
| Pydantic v2 | (already installed) | Request validation via existing models | Already used in `shared/models.py` for all request/response types |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `shared/models.py` | (project) | SearchRequest, BookRequest, ReadRequest, CancelRequest, SearchResponse | Validate all incoming payloads |
| `provider_agent/search.py` | (project) | `search()` and `rescore()` functions | Delegate search action to existing pipeline |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Module-level `_bookings` dict | Class-based BookingStore | Class adds indirection for no benefit in this demo scope — dict is simpler |
| `uuid4().hex[:8]` for IDs | Sequential counter `BK-0001` | UUID avoids collision risk; sequential is more demo-friendly but adds state. Recommend `BK-{uuid4().hex[:6].upper()}` for readable demo IDs |

**Installation:** No new packages needed — all dependencies are already in place.

## Architecture Patterns

### Recommended Project Structure
```
provider_agent/
├── agent.py          # NEW — single entry point, action router + CRUD handlers
├── api_client.py     # Phase 2 — Amadeus API calls
├── scorer.py         # Phase 1 — scoring engine
├── search.py         # Phase 3 — search pipeline (search + rescore)
├── mock_data.py      # Phase 2 — fallback data
└── __init__.py
```

### Pattern 1: Dispatch Dict Router
**What:** Map action strings to handler functions via a dictionary lookup.
**When to use:** When routing a small, known set of actions from a single entry point.
**Why:** Cleaner than if/elif chains, easy to extend, makes the action→handler mapping explicit.

```python
from shared.models import SearchRequest, BookRequest, ReadRequest, CancelRequest

_ACTION_HANDLERS = {
    "search": _handle_search,
    "book": _handle_book,
    "read": _handle_read,
    "cancel": _handle_cancel,
}

def handle_action(payload: dict) -> dict:
    """Single entry point — Orca calls this with a JSON-derived dict."""
    action = payload.get("action")
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        return {"status": "error", "message": f"Unknown action: {action}"}
    return handler(payload)
```

### Pattern 2: Pydantic Validation per Action
**What:** Each handler validates its payload with the corresponding Pydantic model before processing.
**When to use:** Always — the models already exist and catch malformed input early.

```python
def _handle_book(payload: dict) -> dict:
    try:
        request = BookRequest(**payload)
    except ValidationError as e:
        return {"status": "error", "message": str(e)}
    # ... proceed with validated request
```

### Pattern 3: In-Memory Booking Store
**What:** Module-level dict stores bookings keyed by confirmation ID.
**When to use:** Demo/hackathon scope — no persistence needed.

```python
import uuid

_bookings: dict[str, dict] = {}

def _generate_booking_id() -> str:
    return f"BK-{uuid.uuid4().hex[:6].upper()}"
```

### Anti-Patterns to Avoid
- **Storing search results in module state for book lookup:** The CONTEXT.md says agent.py is the single entry point Orca calls. The caller (Consumer Agent) selects an `option_id` from search results and sends it in BookRequest. The book handler needs hotel details for the booking record. **Solution:** Maintain a module-level `_last_search_options` cache that `_handle_search` populates — the book handler looks up the selected hotel from there.
- **Raising exceptions from handlers:** All handlers should return error dicts, never raise. Orca expects a JSON response, not a crash.
- **Coupling book/cancel to real API calls:** Amadeus sandbox is search-only. Book/read/cancel must be fully mocked (locked decision).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Request validation | Manual field checking | Pydantic models from `shared/models.py` | Models already exist with validators, field constraints, type coercion |
| Search pipeline | Duplicate scoring logic | `search.search()` and `search.rescore()` | Phase 3 already handles fetch→score→rank→tag flow |
| UUID generation | Custom ID schemes | `uuid.uuid4()` | Collision-free, zero config |

**Key insight:** Almost everything needed already exists. Phase 4's new code is primarily the router shell and three simple CRUD functions (book/read/cancel) that operate on an in-memory dict.

## Common Pitfalls

### Pitfall 1: Book Handler Can't Find Hotel Details
**What goes wrong:** BookRequest has `option_id` but the handler needs hotel name, price, dates to store a full booking record.
**Why it happens:** Search results are returned to the caller and discarded.
**How to avoid:** Cache the last search results in a module-level `_last_search_options: dict[str, HotelOption]` dict, keyed by option ID. `_handle_search` populates it; `_handle_book` reads from it.
**Warning signs:** Booking record missing hotel name/price fields.

### Pitfall 2: Cancel Refund Logic Ignoring free_cancellation
**What goes wrong:** Cancel always returns "full refund" regardless of hotel policy.
**Why it happens:** Forgetting the locked decision: refund status depends on `free_cancellation` field.
**How to avoid:** Store `free_cancellation` in the booking record at book time. Cancel handler checks it: `True` → "full_refund", `False` → "no_refund"`.
**Warning signs:** All cancellations returning same refund status.

### Pitfall 3: Inconsistent Response Shapes
**What goes wrong:** Search returns a Pydantic model `.model_dump()`, but book/read/cancel return ad-hoc dicts with different key naming.
**Why it happens:** No response models exist for book/read/cancel (only SearchResponse exists in models.py).
**How to avoid:** Define a consistent response envelope: `{"status": "success"|"error", "data": {...}}` for all CRUD operations. Search can wrap its existing SearchResponse in the same envelope or return it directly (it already has `action: "search_results"`).
**Warning signs:** Consumer agent needs different parsing logic per action type.

### Pitfall 4: Forgetting to Return raw_hotels for Rescore
**What goes wrong:** Search works but rescore capability is lost because raw_hotels aren't surfaced.
**Why it happens:** `search()` returns `(SearchResponse, raw_hotels)` tuple but agent.py only returns the response.
**How to avoid:** Cache `raw_hotels` in module state alongside search options. If a future rescore action is needed, it's available. For Phase 4 scope, the search handler should at minimum not discard it.
**Warning signs:** Rescore fails after search succeeds.

## Code Examples

### Complete Router Skeleton

```python
"""
Action router — single entry point for Orca JSON payloads.
"""
from __future__ import annotations

import uuid
from pydantic import ValidationError
from shared.models import (
    SearchRequest, BookRequest, ReadRequest, CancelRequest,
    SearchResponse, HotelOption,
)
from provider_agent.search import search, rescore

# Module state — resets on restart (locked decision)
_bookings: dict[str, dict] = {}
_last_search_options: dict[str, HotelOption] = {}
_last_raw_hotels: list[dict] = []


def _generate_booking_id() -> str:
    return f"BK-{uuid.uuid4().hex[:6].upper()}"


def _handle_search(payload: dict) -> dict:
    request = SearchRequest(**payload)
    response, raw_hotels = search(request)
    # Cache for book handler
    _last_search_options.clear()
    for opt in response.options:
        _last_search_options[opt.id] = opt
    _last_raw_hotels.clear()
    _last_raw_hotels.extend(raw_hotels)
    return response.model_dump(mode="json")


def _handle_book(payload: dict) -> dict:
    request = BookRequest(**payload)
    option = _last_search_options.get(request.option_id)
    if option is None:
        return {"status": "error", "message": f"Unknown option_id: {request.option_id}"}
    booking_id = _generate_booking_id()
    _bookings[booking_id] = {
        "booking_id": booking_id,
        "hotel_name": option.name,
        "hotel_id": option.id,
        "price_per_night": option.price_per_night,
        "check_in": str(request.check_in),
        "check_out": str(request.check_out),
        "guest_name": request.guest_name,
        "free_cancellation": option.free_cancellation,
        "status": "confirmed",
    }
    return {"status": "success", "booking_id": booking_id, "hotel_name": option.name}


def _handle_read(payload: dict) -> dict:
    request = ReadRequest(**payload)
    booking = _bookings.get(request.booking_id)
    if booking is None:
        return {"status": "error", "message": f"Booking not found: {request.booking_id}"}
    return {"status": "success", **booking}


def _handle_cancel(payload: dict) -> dict:
    request = CancelRequest(**payload)
    booking = _bookings.get(request.booking_id)
    if booking is None:
        return {"status": "error", "message": f"Booking not found: {request.booking_id}"}
    booking["status"] = "cancelled"
    refund = "full_refund" if booking.get("free_cancellation") else "no_refund"
    return {"status": "success", "booking_id": request.booking_id, "refund_status": refund}


_ACTION_HANDLERS = {
    "search": _handle_search,
    "book": _handle_book,
    "read": _handle_read,
    "cancel": _handle_cancel,
}


def handle_action(payload: dict) -> dict:
    action = payload.get("action")
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        return {"status": "error", "message": f"Unknown action: {action}"}
    try:
        return handler(payload)
    except ValidationError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Internal error: {e}"}
```

### Error Response Convention

```python
# All error responses follow the same shape:
{"status": "error", "message": "Human-readable description"}

# All success responses for CRUD:
{"status": "success", "booking_id": "BK-A3F2C1", ...extra_fields}

# Search success uses existing SearchResponse format (action: "search_results")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| if/elif action chains | Dispatch dict pattern | Long-standing Python idiom | Cleaner, O(1) lookup, easier to extend |
| Manual dict validation | Pydantic v2 model validation | Pydantic v2 (2023) | Faster validation, better error messages, already in project |

**Deprecated/outdated:**
- None relevant — this phase uses standard Python patterns with no external library concerns.

## Open Questions

1. **Should `handle_action` accept a JSON string or a dict?**
   - What we know: Orca will call this entry point. README shows JSON payloads.
   - What's unclear: Whether Orca passes raw JSON strings or already-parsed dicts.
   - Recommendation: Accept `dict`. If needed, add a thin `handle_action_json(json_str) -> str` wrapper that does `json.loads` / `json.dumps`. Keep the core logic dict-based for testability.

2. **Should rescore be exposed as a separate action?**
   - What we know: Phase 3 built `rescore()` as a separate function. Consumer Agent might send updated weights without a full re-search.
   - What's unclear: Whether the Consumer Agent sends a new `search` action with changed weights (triggering re-fetch) or a dedicated `rescore` action.
   - Recommendation: For Phase 4, only route the four actions from CRUD requirements (search/book/read/cancel). Rescore can be added as a fifth action later if needed — the infrastructure supports it since `_last_raw_hotels` is cached.

## Sources

### Primary (HIGH confidence)
- `shared/models.py` — all Pydantic request/response models, field definitions, validators
- `provider_agent/search.py` — `search()` returns `(SearchResponse, raw_hotels)`, `rescore()` signature
- `provider_agent/api_client.py` — confirms mock fallback behavior, hotel dict structure
- `provider_agent/scorer.py` — `score_and_rank()` produces `list[HotelOption]`
- `provider_agent/mock_data.py` — hotel dict keys: id, name, price_per_night, rating, distance_km, free_cancellation, amenities
- `README.MD` — JSON message formats for all four operations
- `.planning/phases/04-crud-action-routing/04-CONTEXT.md` — locked decisions and discretion areas

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — CRUD-01 through CRUD-04 requirement descriptions
- `.planning/STATE.md` — project decisions history, confirms mock booking approach

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all Python stdlib + existing project code
- Architecture: HIGH — dispatch dict is a well-known Python pattern, all integration points inspected
- Pitfalls: HIGH — identified from direct code inspection of existing modules and locked decisions

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable — no external dependencies or fast-moving libraries)
