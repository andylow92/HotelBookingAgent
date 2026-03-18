"""Provider Agent — hotel search and booking service.

This agent is called by consumer agents via Orca. It:
1. Parses structured JSON requests (search, book, cancel, read)
2. Uses an LLM to generate realistic hotel options for the destination
3. Scores and ranks results using weighted scoring
4. Returns structured JSON responses
"""

import json
import logging
import uuid

import anthropic
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring helpers (mirrors travelneg/provider_agent/scorer.py)
# ---------------------------------------------------------------------------

_FLEXIBILITY_MAP = {"free": 1.0, "partial": 0.3, "none": 0.0}


def _price_score(price: float, max_budget: float) -> float:
    if max_budget <= 0:
        return 0.0
    return max(0.0, 1.0 - price / max_budget)


def _location_score(distance_km: float | None, max_distance_km: float = 5.0) -> float:
    if distance_km is None or max_distance_km <= 0:
        return 0.5
    return max(0.0, 1.0 - distance_km / max_distance_km)


def _rating_score(rating: float) -> float:
    return min(rating / 5.0, 1.0)


def _flexibility_score(flexibility: str) -> float:
    return _FLEXIBILITY_MAP.get(flexibility.lower().strip(), 0.0)


def _match_score(matched: list[str], desired: list[str]) -> float:
    if not desired:
        return 1.0
    count = sum(1 for f in desired if f.lower() in [m.lower() for m in matched])
    return count / len(desired)


def score_and_rank(raw_options: list[dict], request: dict, top_n: int = 3) -> tuple[list[dict], str]:
    """Score raw hotel options, rank them, and generate a negotiation note."""
    weights = request.get("weights", {})
    w_price = weights.get("price", 0.25)
    w_location = weights.get("location", 0.25)
    w_rating = weights.get("rating", 0.20)
    w_flexibility = weights.get("flexibility", 0.15)
    w_match = weights.get("match", 0.15)

    max_budget = request.get("hard_constraints", {}).get("max_price", 200.0)
    desired_features = request.get("context", {}).get("desired_features", [])

    scored = []
    for opt in raw_options:
        ps = _price_score(opt.get("price", 0), max_budget)
        ls = _location_score(opt.get("distance_km"))
        rs = _rating_score(opt.get("rating", 3.0))
        fs = _flexibility_score(opt.get("flexibility", "none"))
        ms = _match_score(opt.get("amenities", []), desired_features)

        total = (
            ps * w_price
            + ls * w_location
            + rs * w_rating
            + fs * w_flexibility
            + ms * w_match
        )

        scored.append({
            "id": opt.get("id", str(uuid.uuid4())[:8]),
            "name": opt.get("name", "Unknown Hotel"),
            "price": opt.get("price", 0),
            "rating": opt.get("rating", 3.0),
            "distance_km": opt.get("distance_km"),
            "flexibility": opt.get("flexibility", "none"),
            "matched_features": [
                f for f in desired_features
                if f.lower() in [a.lower() for a in opt.get("amenities", [])]
            ],
            "amenities": opt.get("amenities", []),
            "total_score": round(total, 4),
            "score_breakdown": {
                "price": round(ps, 4),
                "location": round(ls, 4),
                "rating": round(rs, 4),
                "flexibility": round(fs, 4),
                "match": round(ms, 4),
            },
            "tag": None,
            "raw": opt,
        })

    scored.sort(key=lambda o: o["total_score"], reverse=True)

    if scored:
        cheapest = min(scored, key=lambda o: o["price"])
        cheapest["tag"] = "CHEAPEST"
        highest_rated = max(scored, key=lambda o: o["rating"])
        highest_rated["tag"] = "HIGHEST_RATED"
        scored[0]["tag"] = scored[0]["tag"] or "BEST_BALANCE"

    ranked = scored[:top_n]

    # Generate negotiation note
    if not ranked:
        note = "No options found matching your criteria."
    else:
        parts = []
        top = ranked[0]
        savings_pct = round((1 - top["price"] / max_budget) * 100) if max_budget > 0 else 0
        parts.append(
            f"Top pick: {top['name']} at {top['price']} "
            f"({savings_pct}% under budget, score {top['total_score']})"
        )
        if top["distance_km"] is not None:
            parts.append(f"{top['distance_km']}km from preferred area")
        for opt in ranked[1:]:
            diff = []
            if opt["price"] < top["price"]:
                diff.append(f"cheaper ({opt['price']})")
            if opt["rating"] > top["rating"]:
                diff.append(f"higher rated ({opt['rating']})")
            if opt["distance_km"] is not None and top["distance_km"] is not None:
                if opt["distance_km"] < top["distance_km"]:
                    diff.append(f"closer ({opt['distance_km']}km)")
            tradeoff = ", ".join(diff) if diff else "similar profile"
            parts.append(f"{opt['name']}: {tradeoff} but lower overall score ({opt['total_score']})")
        note = ". ".join(parts) + "."

    return ranked, note


# ---------------------------------------------------------------------------
# LLM-based hotel data generation
# ---------------------------------------------------------------------------

GENERATE_HOTELS_PROMPT = """\
Generate exactly 5 realistic hotel options for a search with these parameters:
- Destination: {destination}
- Check-in: {date_start}
- Check-out: {date_end}
- Guests: {guests}
- Max budget per night: {max_price} {currency}
- Preferred area: {preferred_area}
- Desired features: {desired_features}

Return ONLY a valid JSON array, no markdown fences, no extra text. Each hotel object must have:
{{
  "id": "hotel_<number>",
  "name": "<realistic hotel name for this city>",
  "price": <price per night as float, most within budget but 1-2 can exceed slightly>,
  "rating": <rating 1.0-5.0>,
  "distance_km": <distance from preferred area in km, 0.1-5.0>,
  "flexibility": "<one of: free, partial, none>",
  "amenities": [<list of amenity strings like "wifi", "breakfast", "pool", "gym", "parking", "spa", "restaurant", "bar", "suite", "balcony", "minibar">]
}}

Make the hotels varied: different price points, ratings, distances, and amenity sets.
Include at least one budget option and one premium option.
Use real-sounding hotel names appropriate for {destination}."""


def generate_hotel_options(client: anthropic.Anthropic, request: dict) -> list[dict]:
    """Use Claude to generate realistic hotel options for the destination."""
    destination = request.get("destination", "Unknown")
    date_start = request.get("date_start", "N/A")
    date_end = request.get("date_end", "N/A")
    guests = request.get("guests", 1)
    max_price = request.get("hard_constraints", {}).get("max_price", 200.0)
    currency = request.get("hard_constraints", {}).get("currency", "EUR")
    preferred_area = request.get("context", {}).get("preferred_area") or "city center"
    desired_features = request.get("context", {}).get("desired_features", [])

    prompt = GENERATE_HOTELS_PROMPT.format(
        destination=destination,
        date_start=date_start,
        date_end=date_end,
        guests=guests,
        max_price=max_price,
        currency=currency,
        preferred_area=preferred_area,
        desired_features=", ".join(desired_features) if desired_features else "any",
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    text = response.content[0].text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    return json.loads(text)


# ---------------------------------------------------------------------------
# In-memory booking store
# ---------------------------------------------------------------------------
_bookings: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Main message handler
# ---------------------------------------------------------------------------

async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)
        api_key = variables.get("MADHACK-ANTHROPIC-KEY") or variables.get("ANTHROPIC_API_KEY")

        if not api_key:
            import os
            api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            session.stream(json.dumps({
                "error": "Anthropic API key is not configured for provider agent."
            }))
            session.close()
            return

        client = anthropic.Anthropic(api_key=api_key)

        # Parse the incoming request from consumer agent
        try:
            request = json.loads(data.message)
        except (json.JSONDecodeError, TypeError):
            session.stream(json.dumps({
                "error": "Invalid request format. Expected JSON.",
                "received": data.message[:200] if data.message else None,
            }))
            session.close()
            return

        action = request.get("action")

        if action == "search":
            # Generate hotel options using LLM
            raw_options = generate_hotel_options(client, request)

            # Score and rank
            ranked, negotiation_note = score_and_rank(raw_options, request)

            response = {
                "options": ranked,
                "negotiation_note": negotiation_note,
            }
            session.stream(json.dumps(response))

        elif action == "book":
            option_id = request.get("option_id", "unknown")
            guest_name = request.get("guest_name", "Guest")
            booking_id = f"BK-{uuid.uuid4().hex[:8].upper()}"

            _bookings[booking_id] = {
                "booking_id": booking_id,
                "option_id": option_id,
                "guest_name": guest_name,
                "date_start": request.get("date_start"),
                "date_end": request.get("date_end"),
                "status": "confirmed",
            }

            session.stream(json.dumps({
                "booking_id": booking_id,
                "status": "confirmed",
                "guest_name": guest_name,
                "option_id": option_id,
                "date_start": request.get("date_start"),
                "date_end": request.get("date_end"),
            }))

        elif action == "cancel":
            booking_id = request.get("booking_id", "")
            if booking_id in _bookings:
                _bookings[booking_id]["status"] = "cancelled"
                session.stream(json.dumps({
                    "booking_id": booking_id,
                    "status": "cancelled",
                    "refund": "Full refund will be processed within 5-7 business days.",
                }))
            else:
                session.stream(json.dumps({
                    "booking_id": booking_id,
                    "status": "not_found",
                    "message": "Booking not found. Please check the booking ID.",
                }))

        elif action == "read":
            booking_id = request.get("booking_id", "")
            if booking_id in _bookings:
                session.stream(json.dumps(_bookings[booking_id]))
            else:
                session.stream(json.dumps({
                    "booking_id": booking_id,
                    "status": "not_found",
                    "message": "Booking not found.",
                }))

        else:
            session.stream(json.dumps({
                "error": f"Unknown action: {action}",
                "supported_actions": ["search", "book", "cancel", "read"],
            }))

        session.close()

    except Exception as e:
        logger.exception("Error processing message")
        session.error("Something went wrong.", exception=e)


app, orca = create_agent_app(
    process_message_func=process_message,
    title="Hotel Provider Agent",
    description="Hotel search and booking provider agent. Accepts structured JSON "
    "requests from consumer agents: search (with scoring weights), book, cancel, read. "
    "Returns scored and ranked hotel options with negotiation notes.",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
