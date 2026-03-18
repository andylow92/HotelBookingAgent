"""Nominatim geocoding client + haversine distance.

Uses the free OpenStreetMap Nominatim API (no key required).
Rate-limited to 1 req/s — results are cached in-memory for the session.

Shared between Consumer (resolve preferred area) and Provider (resolve
each result's address to compute real distances).
"""

from __future__ import annotations

import asyncio
from math import atan2, cos, radians, sin, sqrt

import httpx

from travelneg.shared.models import Coords

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_TIMEOUT = 10.0
_USER_AGENT = "TravelNeg/1.0 (hackathon project)"

# Simple in-memory cache: query string → Coords
_cache: dict[str, Coords | None] = {}
# Lock to enforce 1 req/s rate limit
_rate_lock = asyncio.Lock()


def haversine(a: Coords, b: Coords) -> float:
    """Return distance in km between two coordinate pairs."""
    R = 6371.0  # Earth radius in km
    dlat = radians(b.lat - a.lat)
    dlon = radians(b.lon - a.lon)
    h = sin(dlat / 2) ** 2 + cos(radians(a.lat)) * cos(radians(b.lat)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(h), sqrt(1 - h))


async def geocode(
    query: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> Coords | None:
    """Resolve a place name to lat/lon via Nominatim.

    Returns ``None`` if the query cannot be resolved.
    Results are cached so repeated calls for the same query are free.
    """
    key = query.strip().lower()
    if key in _cache:
        return _cache[key]

    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": _USER_AGENT}

    client = http_client or httpx.AsyncClient(timeout=_TIMEOUT)
    should_close = http_client is None

    try:
        async with _rate_lock:
            resp = await client.get(_NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            # Respect Nominatim 1 req/s policy
            await asyncio.sleep(1.0)
    finally:
        if should_close:
            await client.aclose()

    if not data:
        _cache[key] = None
        return None

    coords = Coords(lat=float(data[0]["lat"]), lon=float(data[0]["lon"]))
    _cache[key] = coords
    return coords


async def geocode_batch(
    queries: list[str],
    *,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Coords | None]:
    """Geocode multiple queries sequentially (respects rate limit).

    Returns a dict mapping each query to its Coords (or None).
    """
    results: dict[str, Coords | None] = {}
    for q in queries:
        results[q] = await geocode(q, http_client=http_client)
    return results


def clear_cache() -> None:
    """Clear the geocoding cache (useful in tests)."""
    _cache.clear()
