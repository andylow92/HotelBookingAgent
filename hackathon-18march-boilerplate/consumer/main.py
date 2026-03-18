import json
import logging

import anthropic
from orca import (
    ChatHistoryHelper,
    ChatMessage,
    OrcaHandler,
    Variables,
    create_agent_app,
)

from weather_client import fetch_weather

logger = logging.getLogger(__name__)

# --- Change this once you know the provider slug ---
RESTAURANT_PROVIDER_SLUG = "restaurant-provider"

SYSTEM_PROMPT = """\
You are a friendly restaurant reservation assistant that helps users find and book tables at a restaurant.

You have access to:
- A restaurant provider agent that can search available tables, make reservations, list reservations, and cancel them.
- Real-time weather data for the city (useful for outdoor/patio seating recommendations).

When the user asks about restaurant reservations, extract the following from their message:
- date (YYYY-MM-DD)
- time_slot (must be one of: 11:00, 12:30, 14:00, 18:00, 19:30, 21:00)
- party_size (number of guests)
- location preference (indoor, outdoor, patio, bar) if mentioned
- guest_name and guest_email (for booking)
- any special requests

Today's date is 2026-03-18. If the user says "tonight", "tomorrow", "this Friday", etc., resolve to actual dates.

When you have enough information, respond with a JSON block (and nothing else) wrapped in ```json``` fences:
```json
{
  "action": "search" | "book" | "cancel" | "list",
  "date": "YYYY-MM-DD",
  "time_slot": "HH:MM",
  "party_size": 2,
  "location_pref": "indoor" | "outdoor" | "patio" | "bar" | null,
  "table_id": 1 | null,
  "guest_name": "..." | null,
  "guest_email": "..." | null,
  "special_requests": "..." | null,
  "reservation_id": 1 | null
}
```

If you do NOT have enough information to proceed (e.g. missing date or time), ask the user a friendly follow-up question instead — do NOT output JSON in that case.

For searching, you need at minimum: date, time_slot, and party_size.
For booking, you need: table_id, guest_name, guest_email, date, time_slot, and party_size.
"""

FORMAT_SYSTEM_PROMPT = """\
You are a friendly restaurant reservation assistant. Given table availability or reservation results \
from a provider and optional weather data, compose a helpful, concise response for the user. \
Highlight available tables with their capacity and location. If weather is good, suggest outdoor/patio options. \
Keep it conversational and short. Use markdown formatting for readability (bullet points, bold for \
table numbers/locations). If the provider returned an error, explain it gracefully.
"""


def _build_chat_history(data: ChatMessage) -> list[dict]:
    """Convert Orca chat history to Anthropic messages format."""
    messages = []
    history = ChatHistoryHelper(data.chat_history)
    for msg in history.get_last_n_messages(20):
        # Handle both dict and object access patterns
        if isinstance(msg, dict):
            msg_role = msg.get("role", "")
            msg_content = msg.get("content", "")
        else:
            msg_role = msg.role
            msg_content = msg.content
        role = "user" if msg_role == "user" else "assistant"
        if msg_content:
            messages.append({"role": role, "content": msg_content})
    return messages


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from the LLM response."""
    # Look for ```json ... ``` fenced block
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        raw = text[start:end].strip()
    elif "{" in text and "}" in text:
        start = text.index("{")
        end = text.rindex("}") + 1
        raw = text[start:end]
    else:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _build_provider_request(parsed: dict) -> str:
    """Build a natural-language request for the restaurant provider agent."""
    action = parsed.get("action", "search")

    if action == "search":
        parts = [f"Search for available tables on {parsed.get('date', 'unknown date')}"]
        if parsed.get("time_slot"):
            parts.append(f"at {parsed['time_slot']}")
        if parsed.get("party_size"):
            parts.append(f"for {parsed['party_size']} guest(s)")
        if parsed.get("location_pref"):
            parts.append(f"preferring {parsed['location_pref']} seating")
        return " ".join(parts) + "."

    elif action == "book":
        return json.dumps(
            {
                "action": "book",
                "table_id": parsed.get("table_id"),
                "guest_name": parsed.get("guest_name"),
                "guest_email": parsed.get("guest_email"),
                "date": parsed.get("date"),
                "time_slot": parsed.get("time_slot"),
                "party_size": parsed.get("party_size"),
                "special_requests": parsed.get("special_requests", ""),
            }
        )

    elif action == "cancel":
        return f"Cancel reservation ID {parsed.get('reservation_id')}."

    elif action == "list":
        parts = ["List all reservations"]
        if parsed.get("date"):
            parts.append(f"for {parsed['date']}")
        return " ".join(parts) + "."

    return json.dumps(parsed)


async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)
        anthropic_key = variables.get("MADHACK-ANTHROPIC-KEY")
        weather_key = variables.get("WEATHER_API_KEY")

        if not anthropic_key:
            session.stream("Missing MADHACK-ANTHROPIC-KEY. Please configure it in Orca variables.")
            session.close()
            return

        client = anthropic.Anthropic(api_key=anthropic_key)

        # -- Step 1: Understand user intent --
        session.loading.start("Understanding your request...")

        messages = _build_chat_history(data)
        messages.append({"role": "user", "content": data.message})

        intent_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        intent_text = intent_response.content[0].text
        session.loading.end("Understanding your request...")

        # -- Step 2: Check if LLM needs more info --
        parsed = _extract_json(intent_text)
        if parsed is None:
            # LLM is asking a follow-up question — pass it through
            session.stream(intent_text)
            session.close()
            return

        city = parsed.get("city")
        action = parsed.get("action", "search")

        # -- Step 3: Fetch weather (only for search actions with a city) --
        weather_info = ""
        if city and action == "search" and weather_key:
            session.loading.start("Checking weather...")
            try:
                weather = await fetch_weather(city, api_key=weather_key)
                weather_info = f"\n\nWeather forecast for {city}:\n{weather.summary}"
            except Exception as e:
                logger.warning("Weather fetch failed: %s", e)
                weather_info = ""
            session.loading.end("Checking weather...")

        # -- Step 4: Delegate to restaurant provider --
        session.loading.start("Checking restaurant availability...")

        provider_request = _build_provider_request(parsed)
        try:
            provider_response = session.ask_agent(
                RESTAURANT_PROVIDER_SLUG, provider_request, timeout=120
            )
        except (ValueError, RuntimeError) as e:
            logger.error("Provider agent error: %s", e)
            provider_response = f"Error contacting restaurant provider: {e}"

        session.loading.end("Checking restaurant availability...")

        # -- Step 5: Format final response with Claude --
        session.loading.start("Preparing your results...")

        format_messages = [
            {
                "role": "user",
                "content": (
                    f"User request: {data.message}\n\n"
                    f"Restaurant provider response:\n{provider_response}"
                    f"{weather_info}\n\n"
                    f"Please format a helpful response for the user."
                ),
            }
        ]

        format_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=FORMAT_SYSTEM_PROMPT,
            messages=format_messages,
        )

        session.loading.end("Preparing your results...")
        session.stream(format_response.content[0].text)
        session.close()

    except Exception as e:
        logger.exception("Error processing message")
        session.error("Something went wrong. Please try again.", exception=e)


app, orca = create_agent_app(
    process_message_func=process_message,
    title="Restaurant Reservation Agent",
    description="Personal assistant that finds available tables, checks weather, and helps you book restaurant reservations",
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
