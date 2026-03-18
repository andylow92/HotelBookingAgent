"""
Search pipeline — wires api_client + scorer into a complete search flow.

Two public functions:
- ``search()``  — fetch hotels from API (or mock), score, rank, tag, return top 3.
- ``rescore()`` — re-rank cached raw hotels with new weights, no API call.

Design decisions (locked in 03-CONTEXT.md):
- search() and rescore() are SEPARATE functions (not a mode flag).
- Caller holds the cache — raw hotels passed explicitly to rescore().
- Tags re-assigned on every score_and_rank() call automatically.
- Both return identical SearchResponse format.
"""

from __future__ import annotations

from shared.models import SearchRequest, SearchResponse, Weights
from provider_agent.api_client import search_hotels
from provider_agent.scorer import score_and_rank, generate_negotiation_note


def search(request: SearchRequest) -> tuple[SearchResponse, list[dict]]:
    """Execute full search pipeline: fetch → score → rank → tag.

    Args:
        request: Validated SearchRequest from the consumer agent.

    Returns:
        ``(response, raw_hotels)`` — the SearchResponse with top 3 tagged
        options, plus the raw hotel dicts for the caller to cache (enables
        later rescore without re-fetching).
    """
    # 1. Extract parameters from the request
    destination = request.destination
    check_in = request.check_in
    check_out = request.check_out
    guests = request.guests
    max_budget = request.hard_constraints.max_price_per_night
    desired_amenities = request.context.desired_amenities or None

    # 2. Fetch hotels (API with automatic mock fallback)
    raw_hotels, _is_mock = search_hotels(
        destination, check_in, check_out, guests, max_budget,
    )

    # 3. Score, rank, and tag
    ranked_options = score_and_rank(
        raw_hotels, request.weights, max_budget, desired_amenities,
    )

    # 4. Build response
    note = generate_negotiation_note(ranked_options, request.weights)
    response = SearchResponse(action="search_results", options=ranked_options, negotiation_note=note)

    return response, raw_hotels


def rescore(
    raw_hotels: list[dict],
    weights: Weights,
    max_budget: float,
    desired_amenities: list[str] | None = None,
) -> SearchResponse:
    """Re-rank cached hotels with new weights — no API call.

    Args:
        raw_hotels: Previously fetched hotel dicts (from search()'s second return value).
        weights: New user preference weights.
        max_budget: Maximum price per night from hard constraints.
        desired_amenities: Optional list of desired amenities.

    Returns:
        SearchResponse with freshly scored, ranked, and tagged top 3 options.
    """
    ranked_options = score_and_rank(raw_hotels, weights, max_budget, desired_amenities)
    note = generate_negotiation_note(ranked_options, weights)
    return SearchResponse(action="search_results", options=ranked_options, negotiation_note=note)
