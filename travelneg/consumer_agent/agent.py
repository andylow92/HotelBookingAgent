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

import httpx
from openai import OpenAI

from travelneg.consumer_agent.prompts import SYSTEM_PROMPT, EXTRACT_INTENT_PROMPT
from travelneg.consumer_agent.weight_engine import compute_weights, DEFAULT_WEIGHTS
from travelneg.consumer_agent.weather_client import fetch_weather
from travelneg.shared.geocoding import geocode
from travelneg.shared.models import Weights

logger = logging.getLogger(__name__)


class ConsumerAgent:
    """Stateful consumer agent that manages a conversation session."""

    def __init__(self, openai_api_key: str, domain: str = "hotels"):
        self.client = OpenAI(api_key=openai_api_key)
        self.domain = domain

        # Conversation state (persisted across turns via Orca chat history)
        self.current_weights: Weights = DEFAULT_WEIGHTS
        self.last_search_request: dict | None = None
        self.last_search_results: list[dict] | None = None
        self.last_booking_id: str | None = None

    async def handle_message(self, session, data) -> None:
        """Main entry point — called by the Orca process_message handler."""
        from orca import ChatHistoryHelper

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

    async def _handle_search(self, session, intent: dict) -> None:
        """Build a structured search request and delegate to provider."""
        session.loading.start("Preparing your search...")

        # Extract constraints
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

        # Step 2: Compute scoring weights from user signals
        self.current_weights = compute_weights(preference_signals)

        # Step 3: Enrich with weather data
        weather_context = None
        try:
            weather_api_key = os.environ.get("WEATHER_API_KEY")
            if weather_api_key:
                weather = await fetch_weather(destination, api_key=weather_api_key)
                weather_context = {
                    "summary": weather.summary,
                    "daily": {d: f.model_dump() for d, f in weather.daily.items()},
                }
        except Exception as e:
            logger.warning("Weather API failed: %s", e)

        # Step 4: Enrich with geocoding
        preferred_coords = None
        if preferred_area:
            try:
                coords = await geocode(f"{preferred_area}, {destination}")
                if coords:
                    preferred_coords = {"lat": coords.lat, "lon": coords.lon}
            except Exception as e:
                logger.warning("Geocoding failed: %s", e)

        session.loading.end("Preparing your search...")

        # Step 5: Build the structured request for the provider
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
            "weights": self.current_weights.model_dump(),
            "context": {
                "preferred_area": preferred_area,
                "preferred_area_coords": preferred_coords,
                "weather": weather_context,
                "desired_features": desired_features,
            },
        }
        self.last_search_request = request

        # Step 6: Delegate to provider agent via Orca
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

        # Step 7: Parse provider response and present to user
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

        # Re-compute weights from the new signals, starting from current
        self.current_weights = compute_weights(preference_signals, base=self.current_weights)

        # Update the request
        self.last_search_request["weights"] = self.current_weights.model_dump()
        if desired_features:
            self.last_search_request["context"]["desired_features"] = desired_features

        # Update max_price if provided
        if intent.get("max_price"):
            self.last_search_request["hard_constraints"]["max_price"] = intent["max_price"]

        session.loading.end("Updating your preferences...")

        # Re-delegate to provider
        session.loading.start("Re-searching with your new preferences...")
        session.tracing.begin("Re-negotiation: weights updated", visibility="all")
        session.tracing.append(
            f"New weights: {json.dumps(self.current_weights.model_dump())}"
        )

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
        self._present_results(session, provider_response, weather_ctx, is_update=True)

    async def _handle_book(self, session, intent: dict) -> None:
        """Confirm and delegate a booking to the provider."""
        option_choice = intent.get("option_choice")

        # Resolve option from last search results
        option_id = None
        if self.last_search_results and option_choice:
            try:
                idx = int(option_choice) - 1
                if 0 <= idx < len(self.last_search_results):
                    option_id = self.last_search_results[idx].get("id")
            except (ValueError, TypeError):
                option_id = option_choice

        if not option_id and self.last_search_results:
            # Default to first option
            option_id = self.last_search_results[0].get("id")

        if not option_id:
            session.stream(
                "I don't have any options to book yet. "
                "Let me search first — where would you like to go?"
            )
            session.close()
            return

        guest_name = intent.get("guest_name") or "Guest"
        date_start = None
        date_end = None
        if self.last_search_request:
            date_start = self.last_search_request.get("date_start")
            date_end = self.last_search_request.get("date_end")

        book_request = {
            "action": "book",
            "option_id": option_id,
            "guest_name": guest_name,
            "date_start": date_start,
            "date_end": date_end,
        }

        session.loading.start("Booking your selection...")
        session.tracing.begin("Sending booking request", visibility="all")

        provider_response = self._ask_provider(session, json.dumps(book_request))

        session.tracing.end("Booking processed")
        session.loading.end("Booking your selection...")

        if provider_response:
            # Try to extract booking ID from response
            try:
                resp = json.loads(provider_response)
                self.last_booking_id = resp.get("booking_id")
            except (json.JSONDecodeError, AttributeError):
                pass

            # Present booking confirmation via LLM
            confirmation = self._synthesize_response(
                provider_response,
                "Present this booking confirmation to the user in a friendly way. "
                "Include the confirmation number and any important details like "
                "cancellation policy.",
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

        cancel_request = {
            "action": "cancel",
            "booking_id": booking_id,
        }

        session.loading.start("Cancelling your booking...")
        provider_response = self._ask_provider(session, json.dumps(cancel_request))
        session.loading.end("Cancelling your booking...")

        if provider_response:
            confirmation = self._synthesize_response(
                provider_response,
                "Present this cancellation confirmation to the user in a friendly, "
                "reassuring way. Mention refund details if available.",
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

        read_request = {
            "action": "read",
            "booking_id": booking_id,
        }

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
            session.stream("I couldn't retrieve the booking details. Please try again.")

        session.close()

    def _ask_provider(self, session, message: str) -> str | None:
        """Find and ask the first available provider agent."""
        for agent in session.available_agents:
            try:
                response = session.ask_agent(agent.slug, message, timeout=120)
                return response
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
        # Try to parse structured response
        try:
            resp = json.loads(provider_response)
            self.last_search_results = resp.get("options", [])
        except (json.JSONDecodeError, AttributeError):
            self.last_search_results = None

        # Use LLM to synthesize a friendly response
        extra_context = ""
        if weather_context:
            extra_context += f"\nWeather context: {weather_context.get('summary', '')}"
        if is_update:
            extra_context += (
                "\nThis is an UPDATED recommendation after the user changed preferences. "
                "Mention what changed and why the new top pick is different."
            )

        synthesis_prompt = (
            "You are a friendly travel assistant presenting search results to a user. "
            "Present the top options in a clear, conversational way. "
            "Highlight the top pick and explain tradeoffs using the negotiation_note. "
            "Use the weather context to add helpful advice if relevant. "
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
                        "content": (
                            f"{instruction}\n\n"
                            f"Provider response:\n{provider_data}"
                        ),
                    },
                ],
                temperature=0.7,
                max_tokens=600,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Response synthesis failed: %s", e)
            return provider_data

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
