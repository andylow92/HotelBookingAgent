import logging
import os
from datetime import date

import httpx
import anthropic
from dotenv import load_dotenv
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables

load_dotenv()

logger = logging.getLogger(__name__)

RESTAURANT_TOOLS = [
    {
        "name": "list_time_slots",
        "description": "List all valid reservation time slots for the restaurant.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_tables",
        "description": "List all tables in the restaurant with their capacity and location.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_available_tables",
        "description": "Find tables available for a specific date and time slot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Reservation date (YYYY-MM-DD)"},
                "time_slot": {"type": "string", "description": "Time slot (e.g., 18:00)"},
                "party_size": {"type": "integer", "description": "Number of guests (optional)"},
            },
            "required": ["date", "time_slot"],
        },
    },
    {
        "name": "create_reservation",
        "description": "Create a new restaurant reservation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_id": {"type": "integer", "description": "ID of the table to book"},
                "guest_name": {"type": "string", "description": "Guest's full name"},
                "guest_email": {"type": "string", "description": "Guest's email address"},
                "date": {"type": "string", "description": "Reservation date (YYYY-MM-DD)"},
                "time_slot": {"type": "string", "description": "Time slot (e.g., 18:00)"},
                "party_size": {"type": "integer", "description": "Number of guests"},
                "special_requests": {"type": "string", "description": "Optional special requests"},
            },
            "required": ["table_id", "guest_name", "guest_email", "date", "time_slot", "party_size"],
        },
    },
    {
        "name": "list_reservations",
        "description": "List restaurant reservations, optionally filtered by date and status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Filter by reservation date (YYYY-MM-DD)"},
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
                "reservation_id": {"type": "integer", "description": "Reservation ID"},
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
                "reservation_id": {"type": "integer", "description": "Reservation ID to cancel"},
            },
            "required": ["reservation_id"],
        },
    },
]


def call_restaurant_api(method: str, path: str, api_key: str, base_url: str, **kwargs) -> dict:
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
    if tool_name == "list_time_slots":
        return call_restaurant_api("GET", "/api/time-slots", api_key, base_url)

    elif tool_name == "list_tables":
        return call_restaurant_api("GET", "/api/tables", api_key, base_url)

    elif tool_name == "search_available_tables":
        params = {
            "date": tool_input["date"],
            "time_slot": tool_input["time_slot"],
        }
        if "party_size" in tool_input:
            params["party_size"] = tool_input["party_size"]
        return call_restaurant_api("GET", "/api/tables/available", api_key, base_url, params=params)

    elif tool_name == "create_reservation":
        return call_restaurant_api("POST", "/api/reservations", api_key, base_url, json=tool_input)

    elif tool_name == "list_reservations":
        params = {}
        if "date" in tool_input and tool_input["date"]:
            params["date"] = tool_input["date"]
        if "status" in tool_input and tool_input["status"]:
            params["status"] = tool_input["status"]
        return call_restaurant_api("GET", "/api/reservations", api_key, base_url, params=params)

    elif tool_name == "get_reservation":
        reservation_id = tool_input["reservation_id"]
        return call_restaurant_api("GET", f"/api/reservations/{reservation_id}", api_key, base_url)

    elif tool_name == "cancel_reservation":
        reservation_id = tool_input["reservation_id"]
        return call_restaurant_api("DELETE", f"/api/reservations/{reservation_id}", api_key, base_url)

    return {"error": f"Unknown tool: {tool_name}"}


async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)

        api_key = variables.get("API_KEY") or os.getenv("API_KEY", "")
        base_url = variables.get("API_BASE_URL") or os.getenv(
            "API_BASE_URL", "https://hacketon-18march-api.orcaplatform.ai/restaurant-1"
        )
        anthropic_key = variables.get("MADHACK-ANTHROPIC-KEY") or os.getenv("ANTHROPIC_API_KEY", "")

        if not api_key:
            session.error("API_KEY is not configured.")
            return
        if not anthropic_key:
            session.error("ANTHROPIC_API_KEY is not configured.")
            return

        client = anthropic.Anthropic(api_key=anthropic_key)

        system_prompt = f"""You are Chef Anton's AI Maitre D' for the exclusive 12-table dining experience at "Le Petite Jardin".

Today's date: {date.today().isoformat()}

## About Le Petite Jardin
- **Style**: An intimate, farm-to-table fine dining restaurant with a daily rotating menu based on seasonal ingredients.
- **Atmosphere**: Cozy elegance, candlelit tables, soft jazz, and an exceptional wine pairing service.
- **Locations**: We have tables spread across our beautifully decorated indoor dining room, a vibrant outdoor patio, and a high-end cocktail bar.

## Your Role & Host Approach
1. **Be welcoming and professional** — address the guest warmly, taking into account any special requests or party sizes.
2. **Handle availability gracefully** — we only have 12 tables and 6 time slots (11:00, 12:30, 14:00, 18:00, 19:30, 21:00). If a specific time is full, immediately suggest alternative slots.
3. **Smooth booking flow** — confirm date, time, and party size → search availability → collect name and email → create reservation → share the confirmation ID.
4. **Manage cancellations seamlessly** — assure the guest that their cancellation is handled and invite them to dine with us another time.

## Response Style
- Refined, polite, and accommodating — like a Michelin-star Maitre D'.
- Use plain text (no markdown) in your replies since they appear in a chat interface.
- Keep responses concise but complete. Never leave a guest without a clear next step."""

        messages = [{"role": "user", "content": data.message}]

        while True:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=system_prompt,
                tools=RESTAURANT_TOOLS,
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
    title="Le Petite Jardin — Maitre D' Assistant",
    description="Your exclusive dining assistant for Le Petite Jardin. Book tables, check availability, manage reservations.",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

