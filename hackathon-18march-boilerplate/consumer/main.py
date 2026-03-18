import logging
import os
from datetime import date

import anthropic
import httpx
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables, ChatHistoryHelper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weather helper (OpenWeatherMap 5-day forecast)
# ---------------------------------------------------------------------------

_WEATHER_URL = "https://api.openweathermap.org/data/2.5/forecast"


async def fetch_weather(city: str, api_key: str) -> str:
    """Fetch 5-day forecast for *city* and return a compact text summary."""
    params = {"q": city, "appid": api_key, "units": "metric", "cnt": 40}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(_WEATHER_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    # Bucket by day and summarise
    buckets: dict[str, list[dict]] = {}
    for item in data["list"]:
        day = item["dt_txt"][:10]
        buckets.setdefault(day, []).append(item)

    parts: list[str] = []
    for day in sorted(buckets):
        items = buckets[day]
        temps = [i["main"]["temp"] for i in items]
        conditions = [i["weather"][0]["main"] for i in items]
        condition = max(set(conditions), key=conditions.count)
        avg_temp = round(sum(temps) / len(temps), 1)
        from datetime import datetime
        label = datetime.strptime(day, "%Y-%m-%d").strftime("%A %b %d")
        parts.append(f"{label}: {condition}, {avg_temp}°C")

    return ". ".join(parts) + "."


# ---------------------------------------------------------------------------
# Main message handler — agentic tool-use loop
# ---------------------------------------------------------------------------

async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)
        anthropic_key = (
            variables.get("MADHACK-ANTHROPIC-KEY")
            or os.getenv("ANTHROPIC_API_KEY", "")
        )
        weather_api_key = (
            variables.get("MADHACK-WEATHER-KEY")
            or os.getenv("WEATHER_API_KEY", "")
        )

        if not anthropic_key:
            session.error("ANTHROPIC_API_KEY is not configured.")
            return

        if not weather_api_key:
            logger.warning("WEATHER_API_KEY is not set — weather tool will be disabled.")

        client = anthropic.Anthropic(api_key=anthropic_key)

        # Discover connected hotel agents at runtime
        available_agents = session.available_agents
        if available_agents:
            agent_slugs = [a.slug for a in available_agents]
            agent_descriptions = "\n".join(
                f'- slug: "{a.slug}" | {a.name}: {a.description}'
                for a in available_agents
            )
        else:
            agent_slugs = []
            agent_descriptions = "(no hotel agents connected)"

        # Build tools
        tools = []

        if agent_slugs:
            tools.append({
                "name": "ask_hotel_agent",
                "description": (
                    "Send a message to a connected hotel agent and get its response. "
                    "Use this to search availability, get pricing, create reservations, or cancel bookings. "
                    "You can call multiple hotel agents in sequence to compare options for the user."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "agent_slug": {
                            "type": "string",
                            "description": "The slug of the hotel agent to contact.",
                            "enum": agent_slugs,
                        },
                        "message": {
                            "type": "string",
                            "description": (
                                "The message to send to the hotel agent. Be specific and include "
                                "all relevant details: check-in/check-out dates (YYYY-MM-DD), "
                                "number of guests, guest name and email when booking."
                            ),
                        },
                    },
                    "required": ["agent_slug", "message"],
                },
            })

        if weather_api_key:
            tools.append({
                "name": "get_weather",
                "description": (
                    "Get the 5-day weather forecast for a city. Use this when the user "
                    "mentions a destination so you can include weather context in your "
                    "recommendations (e.g. packing tips, outdoor activity advice)."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name, e.g. 'Berlin' or 'Paris'.",
                        },
                    },
                    "required": ["city"],
                },
            })

        # Include recent conversation history for context
        history = ChatHistoryHelper(data.chat_history)
        recent_messages = history.get_last_n_messages(10)
        messages = recent_messages + [{"role": "user", "content": data.message}]

        # Build weather instructions conditionally
        if weather_api_key:
            weather_step = "2. Check the weather — when the user mentions a destination, use get_weather to fetch the forecast. Include relevant weather context in your recommendations (packing tips, activity suggestions, or warnings about bad weather).\n"
            weather_rule = "- NEVER invent or guess weather data, temperatures, or climate information. Only share weather details you received from the get_weather tool. If the tool fails, do NOT mention weather at all — just silently skip it and focus on the hotel results.\n- When presenting weather, be concise: mention the key conditions and temperatures, don't list every single day unless asked."
        else:
            weather_step = ""
            weather_rule = "- You do NOT have access to weather data. NEVER mention weather, temperatures, climate, or forecasts in any way. Do not suggest the user check a forecast. Just focus on hotels."

        system_prompt = f"""You are Alex, a personal travel assistant. Your job is to help users find and book the best hotel for their trip by consulting connected hotel agents, comparing their options, and completing bookings on the user's behalf.

Today's date: {date.today().isoformat()}

## Connected Hotel Agents
{agent_descriptions}

## How to work
1. Gather requirements — if the user hasn't provided travel dates, number of guests, or any preferences, ask before querying hotels. You need at minimum: check-in date, check-out date, and number of guests.
{weather_step}3. Query hotels — use ask_hotel_agent to search availability. For open-ended requests ("find me a hotel"), check all available agents. For a specific hotel, query only that one.
4. Compare and present — summarize the options side by side: hotel name, available room types, price per night, total cost, and notable perks.
5. Complete the booking — once the user chooses a room, ask for their name and email if not already provided, then call the hotel agent with a reservation request. Pass all required details: room ID, check-in, check-out, guests, name, and email.
6. Confirm — share the reservation ID and a brief summary. Offer to help with anything else.

## Rules
{weather_rule}
- Never invent availability or prices. Always ask the hotel agent.
- When querying for availability, send the dates and guest count in the message to the hotel agent.
- If a hotel agent is unreachable, inform the user and continue with the remaining ones.
- Keep responses friendly and concise. You are the user's advocate."""

        # Agentic loop
        while True:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                assistant_content = response.content
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        if block.name == "ask_hotel_agent":
                            agent_slug = block.input.get("agent_slug")
                            message = block.input.get("message")
                            try:
                                result = session.ask_agent(agent_slug, message)
                            except ValueError:
                                result = f"Agent '{agent_slug}' is not connected."
                            except RuntimeError:
                                result = f"Agent '{agent_slug}' is unavailable or timed out."
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

                        elif block.name == "get_weather":
                            city = block.input.get("city", "")
                            try:
                                result = await fetch_weather(city, weather_api_key)
                            except Exception as e:
                                logger.warning("Weather fetch failed for %s: %s", city, e)
                                result = f"Weather data is unavailable for {city}. Do NOT mention weather at all in your response — skip it entirely."
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # End of agentic loop — stream final text response
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
    title="Personal Travel Assistant",
    description="Alex — your personal travel assistant that searches and compares "
    "connected hotels, checks weather forecasts, and completes bookings on your behalf.",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
