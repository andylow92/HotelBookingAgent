"""Tests for geocoding client and haversine."""

import pytest
import httpx
import respx

from travelneg.shared.geocoding import geocode, haversine, clear_cache
from travelneg.shared.models import Coords


@pytest.fixture(autouse=True)
def _clear_geo_cache():
    clear_cache()
    yield
    clear_cache()


def test_haversine_known_distance():
    # Berlin Alexanderplatz to Berlin Hauptbahnhof ≈ 2.0 km
    alex = Coords(lat=52.5219, lon=13.4132)
    hbf = Coords(lat=52.5251, lon=13.3694)
    dist = haversine(alex, hbf)
    assert 2.5 < dist < 3.5  # rough range


def test_haversine_same_point():
    p = Coords(lat=40.4168, lon=-3.7038)  # Madrid
    assert haversine(p, p) == pytest.approx(0.0, abs=0.001)


def test_haversine_long_distance():
    # Madrid to Berlin ≈ 1870 km
    madrid = Coords(lat=40.4168, lon=-3.7038)
    berlin = Coords(lat=52.5200, lon=13.4050)
    dist = haversine(madrid, berlin)
    assert 1800 < dist < 1950


async def test_geocode_returns_coords():
    mock_response = [{"lat": "52.5219184", "lon": "13.4132147"}]
    with respx.mock:
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        result = await geocode("Alexanderplatz, Berlin")

    assert result is not None
    assert result.lat == pytest.approx(52.52, abs=0.01)
    assert result.lon == pytest.approx(13.41, abs=0.01)


async def test_geocode_returns_none_for_unknown():
    with respx.mock:
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(200, json=[])
        )
        result = await geocode("xyznonexistent12345")

    assert result is None


async def test_geocode_caches_results():
    mock_response = [{"lat": "52.5219184", "lon": "13.4132147"}]
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=mock_response)

    with respx.mock:
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            side_effect=side_effect
        )
        await geocode("Alexanderplatz, Berlin")
        await geocode("Alexanderplatz, Berlin")  # should hit cache
        await geocode("alexanderplatz, berlin")  # normalised → same cache key

    assert call_count == 1
