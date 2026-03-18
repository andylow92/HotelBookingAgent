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
            "API_BASE_URL", "https://hacketon-18march-api.orcaplatform.ai/hotel-1"
        )
        anthropic_key = variables.get("MADHACK-ANTHROPIC-KEY") or os.getenv("ANTHROPIC_API_KEY", "")

        if not api_key:
            session.error("API_KEY is not configured.")
            return
        if not anthropic_key:
            session.error("ANTHROPIC_API_KEY is not configured.")
            return

        client = anthropic.Anthropic(api_key=anthropic_key)

        system_prompt = (
            "You are a hotel booking assistant. Use the provided tools to answer questions "
            "about rooms and reservations. Return concise, data-rich responses in plain text. "
            f"Today's date: {date.today().isoformat()}"
        )

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
    title="Hotel Provider Agent",
    description="Hotel booking provider agent — rooms, availability, pricing, reservations",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
