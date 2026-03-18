import logging
import os
from datetime import date

import anthropic
from dotenv import load_dotenv
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables, ChatHistoryHelper

load_dotenv()

logger = logging.getLogger(__name__)


async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)
        anthropic_key = variables.get("MADHACK-ANTHROPIC-KEY") or os.getenv("ANTHROPIC_API_KEY", "")

        if not anthropic_key:
            session.error("ANTHROPIC_API_KEY is not configured.")
            return

        client = anthropic.Anthropic(api_key=anthropic_key)

        # Known hotel agent slugs (fallback if dynamic discovery is unavailable)
        KNOWN_AGENT_SLUGS = ["clapcito-offers-t5", "clapcito-hotel-assistant-2"]

        # Discover connected hotel agents at runtime
        available_agents = session.available_agents
        if available_agents:
            agent_slugs = [a.slug for a in available_agents]
            agent_descriptions = "\n".join(
                f"- slug: \"{a.slug}\" | {a.name}: {a.description}"
                for a in available_agents
            )
        else:
            # Fall back to known slugs
            agent_slugs = KNOWN_AGENT_SLUGS
            agent_descriptions = "\n".join(
                f"- slug: \"{slug}\""
                for slug in KNOWN_AGENT_SLUGS
            )

        # Build the ask_hotel_agent tool dynamically based on connected agents
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

        # Include recent conversation history for context
        history = ChatHistoryHelper(data.chat_history)
        recent_messages = history.get_last_n_messages(10)
        messages = recent_messages + [{"role": "user", "content": data.message}]

        system_prompt = f"""You are Alex, a personal travel assistant. Your job is to help users find and book the best hotel for their trip by consulting connected hotel agents, comparing their options, and completing bookings on the user's behalf.

Today's date: {date.today().isoformat()}

## Connected Hotel Agents
{agent_descriptions}

## How to work

1. Gather requirements — if the user hasn't provided travel dates, number of guests, or any preferences, ask before querying hotels. You need at minimum: check-in date, check-out date, and number of guests.

2. Query hotels — use ask_hotel_agent to search availability. For open-ended requests ("find me a hotel"), check all available agents. For a specific hotel, query only that one.

3. Compare and present — summarize the options side by side: hotel name, available room types, price per night, total cost, and notable perks. Be concise and help the user decide.

4. Complete the booking — once the user chooses a room, ask for their name and email if not already provided, then call the hotel agent with a reservation request. Pass all required details: room ID, check-in, check-out, guests, name, and email.

5. Confirm — share the reservation ID and a brief summary. Offer to help with anything else.

## Rules
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
    title="Personal Travel Assistant",
    description="Alex — your personal travel assistant that searches and compares connected hotels, checks availability, and completes bookings on your behalf.",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
