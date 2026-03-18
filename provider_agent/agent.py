"""
Action router — the Provider Agent's single entry point.

Orca sends JSON payloads with an ``action`` field; ``handle_action()``
dispatches to the matching handler or returns an error dict.

CRUD lifecycle (all in-memory, resets on restart):
- **search** → delegates to ``provider_agent.search.search()``
- **book**   → stores booking record, returns confirmation ID
- **read**   → retrieves booking by ID
- **cancel** → marks booking cancelled, derives refund from ``free_cancellation``
"""

from __future__ import annotations

import uuid

from pydantic import ValidationError

from shared.models import (
    BookRequest,
    CancelRequest,
    HotelOption,
    ReadRequest,
    SearchRequest,
    SearchResponse,
)
from provider_agent.search import search, rescore  # noqa: F401 — rescore kept for future use


# ---------------------------------------------------------------------------
# Module-level state (in-memory, resets on restart)
# ---------------------------------------------------------------------------

_bookings: dict[str, dict] = {}
"""Booking store keyed by confirmation ID (e.g. ``BK-A1B2C3``)."""

_last_search_options: dict[str, HotelOption] = {}
"""Cached scored options from the most recent search — keyed by option id."""

_last_raw_hotels: list[dict] = []
"""Raw hotel dicts from the most recent search (enables rescore)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_booking_id() -> str:
    """Return a readable demo-friendly booking ID like ``BK-A1B2C3``."""
    return f"BK-{uuid.uuid4().hex[:6].upper()}"


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def _handle_search(payload: dict) -> dict:
    """Validate payload, run search pipeline, cache results."""
    global _last_search_options, _last_raw_hotels

    request = SearchRequest(**payload)
    response, raw_hotels = search(request)

    # Cache for book/rescore
    _last_search_options = {opt.id: opt for opt in response.options}
    _last_raw_hotels = raw_hotels

    return response.model_dump(mode="json")


def _handle_book(payload: dict) -> dict:
    """Validate payload, look up option from last search, store booking."""
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
    """Validate payload, return booking details or error."""
    request = ReadRequest(**payload)

    booking = _bookings.get(request.booking_id)
    if booking is None:
        return {"status": "error", "message": f"Booking not found: {request.booking_id}"}

    return {"status": "success", "booking": booking}


def _handle_cancel(payload: dict) -> dict:
    """Validate payload, cancel booking, derive refund from free_cancellation."""
    request = CancelRequest(**payload)

    booking = _bookings.get(request.booking_id)
    if booking is None:
        return {"status": "error", "message": f"Booking not found: {request.booking_id}"}

    booking["status"] = "cancelled"
    refund = "full_refund" if booking.get("free_cancellation") else "no_refund"

    return {"status": "success", "booking_id": request.booking_id, "refund_status": refund}


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_ACTION_HANDLERS: dict[str, callable] = {
    "search": _handle_search,
    "book": _handle_book,
    "read": _handle_read,
    "cancel": _handle_cancel,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def handle_action(payload: dict) -> dict:
    """Dispatch *payload* to the correct handler based on ``action`` field.

    Always returns a dict — never raises. Unknown actions and validation
    errors produce ``{"status": "error", "message": "..."}``.
    """
    action = payload.get("action")
    handler = _ACTION_HANDLERS.get(action)

    if handler is None:
        return {"status": "error", "message": f"Unknown action: {action}"}

    try:
        return handler(payload)
    except ValidationError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": f"Internal error: {exc}"}
