"""
Amadeus API client with automatic mock-data fallback.

``search_hotels()`` is the single public entry-point.  It tries the
real Amadeus Hotel Search v3 two-step flow and, if *anything* goes
wrong (missing credentials, network error, empty results, unexpected
response shape), silently falls back to ``mock_data.get_mock_hotels()``.

Design decisions (locked):
- No retries — a single failure triggers the fallback immediately.
- ALL exceptions are caught — callers never see errors.
- ``(hotels, is_mock)`` tuple lets callers distinguish data source.
"""

from __future__ import annotations

import logging
import os
from datetime import date

from amadeus import Client, ResponseError  # noqa: F401 — ResponseError used implicitly

from provider_agent.mock_data import get_mock_hotels

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# City-code lookup — extend as needed
# ---------------------------------------------------------------------------

CITY_CODES: dict[str, str] = {
    "Berlin": "BER",
    "berlin": "BER",
    "BERLIN": "BER",
    "Paris": "PAR",
    "paris": "PAR",
    "London": "LON",
    "london": "LON",
    "Madrid": "MAD",
    "madrid": "MAD",
    "Rome": "ROM",
    "rome": "ROM",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> Client | None:
    """Return an Amadeus ``Client`` or *None* when credentials are missing."""
    client_id = os.environ.get("AMADEUS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("AMADEUS_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        logger.info("Amadeus credentials not set — will use mock data")
        return None

    return Client(client_id=client_id, client_secret=client_secret)


def _resolve_city_code(destination: str) -> str:
    """Map a destination name to an IATA-style city code."""
    if destination in CITY_CODES:
        return CITY_CODES[destination]
    # Fallback: first 3 chars uppercased (rough heuristic)
    return destination.upper()[:3]


def _call_amadeus(
    client: Client,
    destination: str,
    check_in: date,
    check_out: date,
    guests: int,
    max_price: float | None,
) -> list:
    """Two-step Amadeus Hotel Search v3 flow.

    Step 1 — Hotel List by city code → hotel IDs.
    Step 2 — Hotel Offers Search with those IDs → offers.

    Raises on any failure so the caller can fall back.
    """
    city_code = _resolve_city_code(destination)

    # Step 1: get hotel IDs for the city
    hotel_list_resp = client.reference_data.locations.hotels.by_city.get(
        cityCode=city_code,
    )
    hotel_ids_all = [h.get("hotelId") for h in (hotel_list_resp.data or [])]
    hotel_ids_all = [hid for hid in hotel_ids_all if hid]  # drop None

    if not hotel_ids_all:
        raise ValueError(f"No hotels found for city code {city_code}")

    # Limit to first 20 IDs (API cap is ~50 — stay safe)
    hotel_ids = hotel_ids_all[:20]

    # Step 2: get offers for those hotels
    params: dict = {
        "hotelIds": hotel_ids,
        "adults": guests,
        "checkInDate": check_in.isoformat(),
        "checkOutDate": check_out.isoformat(),
        "currency": "EUR",
    }
    if max_price is not None and max_price > 0:
        params["priceRange"] = f"0-{int(max_price)}"

    offers_resp = client.shopping.hotel_offers_search.get(**params)
    return offers_resp.data or []


def _normalize_response(raw_data: list, check_in: date, check_out: date) -> list[dict]:
    """Transform Amadeus nested response into flat dicts matching scorer format."""
    num_nights = max((check_out - check_in).days, 1)
    hotels: list[dict] = []

    for item in raw_data:
        hotel_info = item.get("hotel", {})
        offers = item.get("offers", [])
        if not offers:
            continue  # skip hotels with no offers

        offer = offers[0]

        # Price: total for stay → per night
        total_price_str = offer.get("price", {}).get("total", "0")
        try:
            price_per_night = float(total_price_str) / num_nights
        except (ValueError, TypeError):
            price_per_night = 0.0

        # Rating: often None in sandbox — scorer handles it with DEFAULT_RATING
        raw_rating = hotel_info.get("rating")
        rating: float | None = None
        if raw_rating is not None:
            try:
                rating = float(raw_rating)
            except (ValueError, TypeError):
                rating = None

        # Cancellation policy
        cancellations = offer.get("policies", {}).get("cancellations", [])
        free_cancellation = any(
            p.get("type") == "FULL_REFUND" for p in cancellations
        )

        hotels.append(
            {
                "id": hotel_info.get("hotelId", "unknown"),
                "name": hotel_info.get("name", "Unknown Hotel"),
                "price_per_night": price_per_night,
                "rating": rating,
                "distance_km": 0.0,  # not available from offers endpoint
                "amenities": [],  # not in offers response
                "free_cancellation": free_cancellation,
            }
        )

    return hotels


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_hotels(
    destination: str,
    check_in: date,
    check_out: date,
    guests: int,
    max_price: float = 500.0,
) -> tuple[list[dict], bool]:
    """Search for hotels — always returns data, never raises.

    Returns:
        ``(hotels, is_mock)`` where ``is_mock`` is ``True`` when the
        results come from the static fallback data.
    """
    client = _get_client()
    if client is None:
        return get_mock_hotels(), True

    try:
        raw = _call_amadeus(client, destination, check_in, check_out, guests, max_price)
        hotels = _normalize_response(raw, check_in, check_out)
        if not hotels:
            logger.warning("API returned no usable offers — falling back to mock data")
            return get_mock_hotels(), True
        return hotels, False
    except Exception:
        logger.warning("Amadeus API call failed — falling back to mock data", exc_info=True)
        return get_mock_hotels(), True
