"""
Static mock hotel data for Berlin — fallback safety net.

When the Amadeus API is unavailable (missing credentials, errors, timeouts),
the system returns this deterministic data so the demo always works.

Hotels are designed for scoring variety:
- MOCK_BER_01: Budget winner (low price)
- MOCK_BER_06: Rating winner (highest rating, premium price)
- MOCK_BER_03: Balance winner (good across all dimensions)
"""

from __future__ import annotations


def get_mock_hotels() -> list[dict]:
    """Return 7 realistic Berlin hotel dicts matching scorer input format.

    Keys match what ``provider_agent.scorer.score_hotel`` expects:
    id, name, price_per_night, rating, distance_km, free_cancellation, amenities.

    Data is fully static — no randomisation.
    """
    return [
        {
            "id": "MOCK_BER_01",
            "name": "Generator Berlin Mitte",
            "price_per_night": 58.0,
            "rating": 3.4,
            "distance_km": 1.8,
            "free_cancellation": False,
            "amenities": ["wifi", "bar"],
        },
        {
            "id": "MOCK_BER_02",
            "name": "Motel One Berlin-Alexanderplatz",
            "price_per_night": 79.0,
            "rating": 4.1,
            "distance_km": 0.5,
            "free_cancellation": True,
            "amenities": ["wifi", "breakfast", "bar"],
        },
        {
            "id": "MOCK_BER_03",
            "name": "Hotel Indigo Berlin – Ku'damm",
            "price_per_night": 105.0,
            "rating": 4.4,
            "distance_km": 0.8,
            "free_cancellation": True,
            "amenities": ["wifi", "breakfast", "gym", "restaurant"],
        },
        {
            "id": "MOCK_BER_04",
            "name": "nhow Berlin",
            "price_per_night": 142.0,
            "rating": 4.3,
            "distance_km": 1.2,
            "free_cancellation": True,
            "amenities": ["wifi", "breakfast", "gym", "spa", "restaurant", "bar"],
        },
        {
            "id": "MOCK_BER_05",
            "name": "Holiday Inn Express Berlin City Centre",
            "price_per_night": 88.0,
            "rating": 3.8,
            "distance_km": 2.1,
            "free_cancellation": False,
            "amenities": ["wifi", "breakfast", "parking"],
        },
        {
            "id": "MOCK_BER_06",
            "name": "Hotel Adlon Kempinski Berlin",
            "price_per_night": 189.0,
            "rating": 4.8,
            "distance_km": 0.2,
            "free_cancellation": True,
            "amenities": ["wifi", "breakfast", "pool", "gym", "spa", "restaurant", "bar", "parking"],
        },
        {
            "id": "MOCK_BER_07",
            "name": "Grimm's Hotel Berlin Mitte",
            "price_per_night": 72.0,
            "rating": 3.9,
            "distance_km": 3.2,
            "free_cancellation": False,
            "amenities": ["wifi", "parking"],
        },
    ]
