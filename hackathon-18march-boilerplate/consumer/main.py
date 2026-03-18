"""Consumer Agent — personal travel assistant.

This agent is user-facing. It:
1. Parses user intent using an LLM
2. Enriches requests with weather + geocoding data
3. Delegates to provider agents via Orca (session.ask_agent)
4. Presents results back to the user in a friendly way
5. Handles re-negotiation when user changes constraints

It NEVER calls travel APIs directly or makes up listings.
"""

import json
import logging
import os

from openai import OpenAI
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables, ChatHistoryHelper

from prompts import SYSTEM_PROMPT, EXTRACT_INTENT_PROMPT
from weight_engine import compute_weights, DEFAULT_WEIGHTS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Consumer Agent class
# ---------------------------------------------------------------------------

class ConsumerAgent:
    """Stateful consumer agent that manages a single conversation turn."""

    def __init__(self, openai_api_key: str, domain: str = "hotels"):
        self.client = OpenAI(api_key=openai_api_key)
        self.domain = domain

        # Conversation state
        self.current_weights: dict = dict(DEFAULT_WEIGHTS)
        self.last_search_request: dict | None = None
        self.last_search_results: list[dict] | None = None
        self.last_booking_id: str | None = None

    async def handle_message(self, session, data: ChatMessage) -> None:
        """Main entry point — called by the Orca process_message handler."""
        session.loading.start("Understanding your request...")

        # Build chat history context
        history = ChatHistoryHelper(data.chat_history)
        recent = history.get_last_n_messages(10)
        history_text = self._format_history(recent)

        # Step 1: Extract intent using LLM
        intent = self._extract_intent(data.message, history_text)
        session.loading.end("Understanding your request...")

        if intent.get("intent") == "unclear":
            session.stream(
                "I'd love to help! Could you tell me more about what you're looking for? "
                "For example: destination, dates, budget, or any preferences?"
            )
            session.close()
            return

        # Route by intent
        if intent["intent"] == "search":
            await self._handle_search(session, intent)
        elif intent["intent"] == "change":
            await self._handle_renegotiation(session, intent)
        elif intent["intent"] == "book":
            await self._handle_book(session, intent)
        elif intent["intent"] == "cancel":
            await self._handle_cancel(session, intent)
        elif intent["intent"] == "read":
            await self._handle_read(session, intent)
        else:
            session.stream(
                "I can help you search, book, or cancel travel services. "
                "Just tell me what you're looking for!"
            )
            session.close()

    # ------------------------------------------------------------------
    # Intent handlers — each one delegates to provider, never calls APIs
    # ------------------------------------------------------------------

    async def _handle_search(self, session, intent: dict) -> None:
        """Build a structured search request and delegate to provider."""
        session.loading.start("Preparing your search...")

        destination = intent.get("destination")
        if not destination:
            session.loading.end("Preparing your search...")
            session.stream(
                "Where would you like to go? Please mention a city or destination."
            )
            session.close()
            return

        date_start = intent.get("date_start")
        date_end = intent.get("date_end")
        guests = intent.get("guests") or 1
        max_price = intent.get("max_price") or 200.0
        currency = intent.get("currency") or "EUR"
        preferred_area = intent.get("preferred_area")
        desired_features = intent.get("desired_features") or []
        preference_signals = intent.get("preference_signals") or []

        # Compute scoring weights from user signals
        self.current_weights = compute_weights(preference_signals)

        # Enrich with weather data
        weather_context = await self._fetch_weather_safe(destination)

        # Enrich with geocoding
        preferred_coords = None
        if preferred_area:
            preferred_coords = await self._geocode_safe(
                f"{preferred_area}, {destination}"
            )

        session.loading.end("Preparing your search...")

        # Build the structured request for the provider
        request = {
            "action": "search",
            "domain": self.domain,
            "destination": destination,
            "date_start": date_start,
            "date_end": date_end,
            "guests": guests,
            "hard_constraints": {
                "max_price": max_price,
                "currency": currency,
            },
            "weights": self.current_weights,
            "context": {
                "preferred_area": preferred_area,
                "preferred_area_coords": preferred_coords,
                "weather": weather_context,
                "desired_features": desired_features,
            },
        }
        self.last_search_request = request

        # Delegate to provider agent via Orca
        session.loading.start("Searching for the best options...")
        session.tracing.begin("Delegating to provider agent", visibility="all")

        provider_response = self._ask_provider(session, json.dumps(request))

        session.tracing.end("Provider responded")
        session.loading.end("Searching for the best options...")

        if not provider_response:
            session.stream(
                "I couldn't reach the provider agent right now. Please try again."
            )
            session.close()
            return

        self._present_results(session, provider_response, weather_context)

    async def _handle_renegotiation(self, session, intent: dict) -> None:
        """User changed their mind — re-weight and re-delegate."""
        if not self.last_search_request:
            session.stream(
                "I don't have a previous search to update. "
                "Tell me what you're looking for and I'll find options!"
            )
            session.close()
            return

        session.loading.start("Updating your preferences...")

        preference_signals = intent.get("preference_signals") or []
        desired_features = intent.get("desired_features") or []

        self.current_weights = compute_weights(
            preference_signals, base=self.current_weights
        )

        self.last_search_request["weights"] = self.current_weights
        if desired_features:
            self.last_search_request["context"]["desired_features"] = desired_features
        if intent.get("max_price"):
            self.last_search_request["hard_constraints"]["max_price"] = intent[
                "max_price"
            ]

        session.loading.end("Updating your preferences...")

        session.loading.start("Re-searching with your new preferences...")
        session.tracing.begin("Re-negotiation: weights updated", visibility="all")
        session.tracing.append(f"New weights: {json.dumps(self.current_weights)}")

        provider_response = self._ask_provider(
            session, json.dumps(self.last_search_request)
        )

        session.tracing.end("Provider responded with re-scored results")
        session.loading.end("Re-searching with your new preferences...")

        if not provider_response:
            session.stream("I couldn't reach the provider. Please try again.")
            session.close()
            return

        weather_ctx = self.last_search_request.get("context", {}).get("weather")
        self._present_results(
            session, provider_response, weather_ctx, is_update=True
        )

    async def _handle_book(self, session, intent: dict) -> None:
        """Confirm and delegate a booking to the provider."""
        option_choice = intent.get("option_choice")

        option_id = None
        if self.last_search_results and option_choice:
            try:
                idx = int(option_choice) - 1
                if 0 <= idx < len(self.last_search_results):
                    option_id = self.last_search_results[idx].get("id")
            except (ValueError, TypeError):
                option_id = option_choice

        if not option_id and self.last_search_results:
            option_id = self.last_search_results[0].get("id")

        if not option_id:
            session.stream(
                "I don't have any options to book yet. "
                "Let me search first — where would you like to go?"
            )
            session.close()
            return

        guest_name = intent.get("guest_name") or "Guest"
        date_start = (self.last_search_request or {}).get("date_start")
        date_end = (self.last_search_request or {}).get("date_end")

        book_request = {
            "action": "book",
            "option_id": option_id,
            "guest_name": guest_name,
            "date_start": date_start,
            "date_end": date_end,
        }

        session.loading.start("Booking your selection...")
        provider_response = self._ask_provider(session, json.dumps(book_request))
        session.loading.end("Booking your selection...")

        if provider_response:
            try:
                resp = json.loads(provider_response)
                self.last_booking_id = resp.get("booking_id")
            except (json.JSONDecodeError, AttributeError):
                pass

            confirmation = self._synthesize_response(
                provider_response,
                "Present this booking confirmation to the user in a friendly way. "
                "Include the confirmation number and any important details.",
            )
            session.stream(confirmation)
        else:
            session.stream("I couldn't complete the booking. Please try again.")

        session.close()

    async def _handle_cancel(self, session, intent: dict) -> None:
        """Delegate a cancellation to the provider."""
        booking_id = intent.get("booking_id") or self.last_booking_id

        if not booking_id:
            session.stream(
                "I don't have a booking to cancel. "
                "Could you provide the booking or confirmation number?"
            )
            session.close()
            return

        cancel_request = {"action": "cancel", "booking_id": booking_id}

        session.loading.start("Cancelling your booking...")
        provider_response = self._ask_provider(session, json.dumps(cancel_request))
        session.loading.end("Cancelling your booking...")

        if provider_response:
            confirmation = self._synthesize_response(
                provider_response,
                "Present this cancellation confirmation in a friendly, reassuring way. "
                "Mention refund details if available.",
            )
            session.stream(confirmation)
        else:
            session.stream("I couldn't process the cancellation. Please try again.")

        session.close()

    async def _handle_read(self, session, intent: dict) -> None:
        """Delegate a booking read to the provider."""
        booking_id = intent.get("booking_id") or self.last_booking_id

        if not booking_id:
            session.stream("Could you provide your booking or confirmation number?")
            session.close()
            return

        read_request = {"action": "read", "booking_id": booking_id}

        session.loading.start("Fetching your booking details...")
        provider_response = self._ask_provider(session, json.dumps(read_request))
        session.loading.end("Fetching your booking details...")

        if provider_response:
            summary = self._synthesize_response(
                provider_response,
                "Present these booking details to the user in a clear, friendly way.",
            )
            session.stream(summary)
        else:
            session.stream(
                "I couldn't retrieve the booking details. Please try again."
            )

        session.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ask_provider(self, session, message: str) -> str | None:
        """Find and ask the first available provider agent."""
        for agent in session.available_agents:
            try:
                return session.ask_agent(agent.slug, message, timeout=120)
            except (ValueError, RuntimeError) as e:
                logger.warning("Provider agent %s failed: %s", agent.slug, e)
                continue
        return None

    def _present_results(
        self,
        session,
        provider_response: str,
        weather_context: dict | None,
        is_update: bool = False,
    ) -> None:
        """Parse provider response and present results to the user."""
        try:
            resp = json.loads(provider_response)
            self.last_search_results = resp.get("options", [])
        except (json.JSONDecodeError, AttributeError):
            self.last_search_results = None

        extra_context = ""
        if weather_context:
            extra_context += f"\nWeather: {weather_context.get('summary', '')}"
        if is_update:
            extra_context += (
                "\nThis is an UPDATED recommendation after the user changed preferences. "
                "Mention what changed and why the new top pick is different."
            )

        synthesis_prompt = (
            "Present the search results to the user in a friendly, conversational way. "
            "Highlight the top pick and explain tradeoffs using the negotiation_note. "
            "Use weather context to add helpful advice if relevant. "
            "End by asking if they'd like to book or adjust preferences."
            f"{extra_context}"
        )

        friendly_response = self._synthesize_response(provider_response, synthesis_prompt)
        session.stream(friendly_response)
        session.close()

    def _extract_intent(self, user_message: str, chat_history: str) -> dict:
        """Use LLM to extract structured intent from user message."""
        prompt = EXTRACT_INTENT_PROMPT.format(
            user_message=user_message,
            chat_history=chat_history,
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            content = response.choices[0].message.content.strip()
            return json.loads(content)
        except (json.JSONDecodeError, Exception) as e:
            logger.error("Intent extraction failed: %s", e)
            return {"intent": "unclear"}

    def _synthesize_response(self, provider_data: str, instruction: str) -> str:
        """Use LLM to turn provider data into a friendly user-facing response."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"{instruction}\n\nProvider response:\n{provider_data}",
                    },
                ],
                temperature=0.7,
                max_tokens=600,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Response synthesis failed: %s", e)
            return provider_data

    async def _fetch_weather_safe(self, destination: str) -> dict | None:
        """Fetch weather, returning None on any failure."""
        try:
            api_key = os.environ.get("WEATHER_API_KEY")
            if not api_key:
                return None
            from weather_client import fetch_weather

            return await fetch_weather(destination, api_key=api_key)
        except Exception as e:
            logger.warning("Weather API failed: %s", e)
            return None

    async def _geocode_safe(self, query: str) -> dict | None:
        """Geocode a place, returning None on any failure."""
        try:
            from geocoding import geocode

            return await geocode(query)
        except Exception as e:
            logger.warning("Geocoding failed: %s", e)
            return None

    def _format_history(self, messages) -> str:
        """Format chat history messages into a text block for context."""
        if not messages:
            return "(no prior messages)"
        lines = []
        for msg in messages:
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", str(msg))
            lines.append(f"{role}: {content}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orca app entry point
# ---------------------------------------------------------------------------

async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)
        openai_key = variables.get("OPENAI_API_KEY")

        if not openai_key:
            session.stream(
                "OpenAI API key is not configured. "
                "Please set the OPENAI_API_KEY variable in Orca."
            )
            session.close()
            return

        domain = variables.get("DOMAIN") or "hotels"

        agent = ConsumerAgent(openai_api_key=openai_key, domain=domain)
        await agent.handle_message(session, data)

    except Exception as e:
        logger.exception("Error processing message")
        session.error("Something went wrong.", exception=e)


app, orca = create_agent_app(
    process_message_func=process_message,
    title="Consumer Agent",
    description="Personal travel assistant — understands your preferences, "
    "enriches with weather and location data, and delegates to provider agents. "
    "Never calls travel APIs directly.",
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
