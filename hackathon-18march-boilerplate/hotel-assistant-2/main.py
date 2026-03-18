import logging
import os
from datetime import date

import httpx
import anthropic
from dotenv import load_dotenv
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables

load_dotenv()

logger = logging.getLogger(__name__)

HOTEL_TOOLS = [
    {
        "name": "list_rooms",
        "description": "List all available room types at the hotel.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_available_rooms",
        "description": "Search for available rooms for specific dates and number of guests.",
        "input_schema": {
            "type": "object",
            "properties": {
                "check_in": {"type": "string", "description": "Check-in date (YYYY-MM-DD)"},
                "check_out": {"type": "string", "description": "Check-out date (YYYY-MM-DD)"},
                "guests": {"type": "integer", "description": "Number of guests"},
            },
            "required": ["check_in", "check_out", "guests"],
        },
    },
    {
        "name": "get_pricing",
        "description": "Get detailed pricing breakdown for a specific room and dates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string", "description": "Room ID"},
                "check_in": {"type": "string", "description": "Check-in date (YYYY-MM-DD)"},
                "check_out": {"type": "string", "description": "Check-out date (YYYY-MM-DD)"},
            },
            "required": ["room_id", "check_in", "check_out"],
        },
    },
    {
        "name": "create_reservation",
        "description": "Create a hotel reservation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string", "description": "Room ID to book"},
                "check_in": {"type": "string", "description": "Check-in date (YYYY-MM-DD)"},
                "check_out": {"type": "string", "description": "Check-out date (YYYY-MM-DD)"},
                "num_guests": {"type": "integer", "description": "Number of guests"},
                "guest_name": {"type": "string", "description": "Name of the main guest"},
                "guest_email": {"type": "string", "description": "Email of the main guest"},
            },
            "required": ["room_id", "check_in", "check_out", "num_guests", "guest_name", "guest_email"],
        },
    },
    {
        "name": "list_reservations",
        "description": "List hotel reservations, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status (e.g. confirmed, cancelled)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_reservation",
        "description": "Get details of a specific reservation by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string", "description": "Reservation ID"},
            },
            "required": ["reservation_id"],
        },
    },
    {
        "name": "cancel_reservation",
        "description": "Cancel a reservation by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string", "description": "Reservation ID to cancel"},
            },
            "required": ["reservation_id"],
        },
    },
]


def call_hotel_api(method: str, path: str, api_key: str, base_url: str, **kwargs) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"X-API-Key": api_key}
    with httpx.Client(timeout=30) as client:
        response = client.request(method, url, headers=headers, **kwargs)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {response.status_code}: {response.text}"}
        return response.json()


def execute_tool(tool_name: str, tool_input: dict, api_key: str, base_url: str) -> dict:
    if tool_name == "list_rooms":
        return call_hotel_api("GET", "/api/rooms", api_key, base_url)

    elif tool_name == "search_available_rooms":
        params = {
            "check_in": tool_input["check_in"],
            "check_out": tool_input["check_out"],
            "guests": tool_input["guests"],
        }
        return call_hotel_api("GET", "/api/rooms/available", api_key, base_url, params=params)

    elif tool_name == "get_pricing":
        params = {
            "room_id": tool_input["room_id"],
            "check_in": tool_input["check_in"],
            "check_out": tool_input["check_out"],
        }
        return call_hotel_api("GET", "/api/pricing", api_key, base_url, params=params)

    elif tool_name == "create_reservation":
        return call_hotel_api("POST", "/api/reservations", api_key, base_url, json=tool_input)

    elif tool_name == "list_reservations":
        params = {}
        if "status" in tool_input and tool_input["status"]:
            params["status"] = tool_input["status"]
        return call_hotel_api("GET", "/api/reservations", api_key, base_url, params=params)

    elif tool_name == "get_reservation":
        reservation_id = tool_input["reservation_id"]
        return call_hotel_api("GET", f"/api/reservations/{reservation_id}", api_key, base_url)

    elif tool_name == "cancel_reservation":
        reservation_id = tool_input["reservation_id"]
        return call_hotel_api("DELETE", f"/api/reservations/{reservation_id}", api_key, base_url)

    return {"error": f"Unknown tool: {tool_name}"}


async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)

        api_key = variables.get("API_KEY") or os.getenv("API_KEY", "")
        base_url = variables.get("API_BASE_URL") or os.getenv(
            "API_BASE_URL", "https://hacketon-18march-api.orcaplatform.ai/hotel-2"
        )
        anthropic_key = variables.get("MADHACK-ANTHROPIC-KEY") or os.getenv("ANTHROPIC_API_KEY", "")

        if not api_key:
            session.error("API_KEY is not configured.")
            return
        if not anthropic_key:
            session.error("ANTHROPIC_API_KEY is not configured.")
            return

        client = anthropic.Anthropic(api_key=anthropic_key)

        system_prompt = f"""You are Sol, the friendly booking assistant of **Casa del Sol Boutique Hotel** — a charming, sun-drenched retreat inspired by Mediterranean coastal living. Known for its laid-back luxury, vibrant local culture, and genuine warmth, Casa del Sol is the perfect escape from the everyday.

Today's date: {date.today().isoformat()}

## About Casa del Sol Boutique Hotel
- **Style**: Relaxed Mediterranean luxury. Think whitewashed walls, terracotta tiles, a lush central courtyard with a mosaic pool, rooftop sunset bar "La Terraza", and a farm-to-table restaurant "El Patio" featuring local seasonal cuisine.
- **Location**: Beachside village district, steps from the waterfront promenade, artisan markets, and boat tours. 10 minutes from the old town.
- **Clientele**: Couples on romantic getaways, families looking for a real vacation, digital nomads seeking inspiration, and adventure travelers using us as a home base.

## Room Portfolio
- **Single rooms** (101, 102) — $89/night. Cozy sun-filled rooms with garden views. Perfect for solo travelers. Includes artisanal breakfast basket, free bike rental, and high-speed Wi-Fi.
- **Double rooms** (201-302) — from $129/night. Bright, airy rooms with either courtyard or partial sea views. Handcrafted furniture, local pottery, and a private terrace on upper floors. Great for couples or travel partners.
- **Suites** (401, 402, 501) — from $229/night. The full Casa del Sol experience. Private plunge pool or sea-view balcony, outdoor rainfall shower, curated welcome amenity with local wines and charcuterie. Room 501 is our Vista Suite — a two-floor loft sleeping up to 6, with a private rooftop and panoramic sea views.

## Your Role & Sales Approach
1. **Be warm and personable** — guests chose a boutique hotel for a reason. Match their energy. Ask what brings them here: anniversary, family trip, remote work, adventure?
2. **Sell the experience, not just the room** — mention El Patio's seafood paella, the sunset yoga sessions on La Terraza, or the hotel's guided snorkeling tours when relevant.
3. **Upsell the suite naturally** — the plunge pool and welcome amenity are conversation starters. If someone books for a special occasion, suggest the suite without hesitation.
4. **Promote value-adds** — all double and suite bookings include a complimentary welcome drink at La Terraza. Stays of 4+ nights get a free half-day boat excursion. Always mention these perks.
5. **Urgency when relevant** — if peak-season availability is tight, let the guest know so they feel confident booking now.
6. **Smooth booking flow** — guide guests step by step: confirm purpose of trip → suggest best room → confirm dates & guests → collect name & email → create reservation → confirm with reservation ID and a warm send-off.
7. **Handle cancellations with empathy** — offer alternative dates or suggest gift vouchers if they want to keep their Casa del Sol experience for another time.

## Response Style
- Friendly, warm, and enthusiastic — like a local friend who happens to run the best hotel in town.
- Use plain text (no markdown) in your replies since they appear in a chat interface.
- Keep responses inviting and natural. Paint a small picture when describing rooms — help guests feel excited.
- Always end with a question or a clear next step to keep the conversation flowing."""

        messages = [{"role": "user", "content": data.message}]

        while True:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=system_prompt,
                tools=HOTEL_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                tool_results = []
                assistant_content = response.content

                for block in response.content:
                    if block.type == "tool_use":
                        result = execute_tool(block.name, block.input, api_key, base_url)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            else:
                for block in response.content:
                    if hasattr(block, "text"):
                        session.stream(block.text)
                break

    except Exception as e:
        logger.exception("Error processing message")
        session.error("Something went wrong.", exception=e)

    finally:
        session.close()


app, orca = create_agent_app(
    process_message_func=process_message,
    title="Casa del Sol Boutique Hotel — Sol Assistant",
    description="Sol, your friendly booking assistant at Casa del Sol. Book rooms, check availability, manage reservations.",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
