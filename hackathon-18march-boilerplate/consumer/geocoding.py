"""Nominatim geocoding client.

Uses the free OpenStreetMap Nominatim API (no key required).
Rate-limited to 1 req/s — results are cached in-memory for the session.
"""

import asyncio
import httpx

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_TIMEOUT = 10.0
_USER_AGENT = "TravelNeg/1.0 (hackathon project)"
_cache: dict[str, dict | None] = {}
_rate_lock = asyncio.Lock()


async def geocode(query: str) -> dict | None:
    """Resolve a place name to {"lat": float, "lon": float} via Nominatim.

    Results are cached so repeated calls for the same query are free.
    """
    key = query.strip().lower()
    if key in _cache:
        return _cache[key]

    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": _USER_AGENT}

    async with _rate_lock:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            await asyncio.sleep(1.0)  # Rate limit: 1 req/s

    if not data:
        _cache[key] = None
        return None

    coords = {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
    _cache[key] = coords
    return coords
