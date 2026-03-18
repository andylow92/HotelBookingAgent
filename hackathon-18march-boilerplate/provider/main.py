import json
import logging

import anthropic
import httpx
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a restaurant reservation assistant that processes requests and decides which API calls to make.

Available actions (respond with a JSON block):

1. **search** — Find available tables
```json
{"action": "search", "date": "YYYY-MM-DD", "time_slot": "HH:MM", "party_size": N}
```

2. **book** — Make a reservation
```json
{"action": "book", "table_id": N, "guest_name": "...", "guest_email": "...", "date": "YYYY-MM-DD", "time_slot": "HH:MM", "party_size": N, "special_requests": "..."}
```

3. **cancel** — Cancel a reservation
```json
{"action": "cancel", "reservation_id": N}
```

4. **list** — List reservations (optionally filtered)
```json
{"action": "list", "date": "YYYY-MM-DD or null", "status": "confirmed or cancelled or null"}
```

5. **get_reservation** — Get a single reservation
```json
{"action": "get_reservation", "reservation_id": N}
```

6. **time_slots** — List valid time slots
```json
{"action": "time_slots"}
```

7. **tables** — List all tables
```json
{"action": "tables"}
```

Valid time slots: 11:00, 12:30, 14:00, 18:00, 19:30, 21:00
Valid locations: indoor, outdoor, patio, bar

Today's date is 2026-03-18. Resolve relative dates like "tonight", "tomorrow", "this Friday" to actual YYYY-MM-DD dates.

Always respond with ONLY a JSON block. No extra text.
"""


async def call_api(client: httpx.AsyncClient, method: str, path: str,
                   params: dict = None, json_body: dict = None) -> dict:
    """Call the restaurant API and return parsed JSON."""
    url = path
    kwargs = {}
    if params:
        kwargs["params"] = params
    if json_body:
        kwargs["json"] = json_body

    resp = await client.request(method, url, **kwargs)
    resp.raise_for_status()
    return resp.json()


async def handle_action(client: httpx.AsyncClient, action_data: dict) -> str:
    """Execute the appropriate API call based on the parsed action."""
    action = action_data.get("action", "search")

    try:
        if action == "time_slots":
            result = await call_api(client, "GET", "/api/time-slots")
            return json.dumps(result, indent=2)

        elif action == "tables":
            result = await call_api(client, "GET", "/api/tables")
            return json.dumps(result, indent=2)

        elif action == "search":
            params = {
                "date": action_data["date"],
                "time_slot": action_data["time_slot"],
            }
            if action_data.get("party_size"):
                params["party_size"] = action_data["party_size"]
            result = await call_api(client, "GET", "/api/tables/available", params=params)
            return json.dumps(result, indent=2)

        elif action == "book":
            body = {
                "table_id": action_data["table_id"],
                "guest_name": action_data["guest_name"],
                "guest_email": action_data["guest_email"],
                "date": action_data["date"],
                "time_slot": action_data["time_slot"],
                "party_size": action_data["party_size"],
            }
            if action_data.get("special_requests"):
                body["special_requests"] = action_data["special_requests"]
            result = await call_api(client, "POST", "/api/reservations", json_body=body)
            return json.dumps(result, indent=2)

        elif action == "cancel":
            rid = action_data["reservation_id"]
            result = await call_api(client, "DELETE", f"/api/reservations/{rid}")
            return json.dumps(result, indent=2)

        elif action == "list":
            params = {}
            if action_data.get("date"):
                params["date"] = action_data["date"]
            if action_data.get("status"):
                params["status"] = action_data["status"]
            result = await call_api(client, "GET", "/api/reservations", params=params)
            return json.dumps(result, indent=2)

        elif action == "get_reservation":
            rid = action_data["reservation_id"]
            result = await call_api(client, "GET", f"/api/reservations/{rid}")
            return json.dumps(result, indent=2)

        else:
            return json.dumps({"error": f"Unknown action: {action}"})

    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        try:
            error_body = e.response.json()
        except Exception:
            pass
        return json.dumps({
            "error": f"API returned {e.response.status_code}",
            "detail": error_body,
        }, indent=2)


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from the LLM response."""
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


async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)
        api_key = variables.get("API_KEY")
        api_base_url = variables.get("API_BASE_URL")
        anthropic_key = variables.get("MADHACK-ANTHROPIC-KEY")

        if not api_key:
            session.stream("Missing API_KEY variable. Please configure it in Orca.")
            session.close()
            return

        if not api_base_url:
            session.stream("Missing API_BASE_URL variable. Please configure it in Orca.")
            session.close()
            return

        if not anthropic_key:
            session.stream("Missing MADHACK-ANTHROPIC-KEY variable. Please configure it in Orca.")
            session.close()
            return

        # Set up HTTP client with API key auth
        http_client = httpx.AsyncClient(
            base_url=api_base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=30.0,
        )

        # Use Claude to understand the incoming request
        llm_client = anthropic.Anthropic(api_key=anthropic_key)

        response = llm_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": data.message}],
        )
        intent_text = response.content[0].text

        parsed = _extract_json(intent_text)
        if parsed is None:
            session.stream(f"Could not understand the request: {intent_text}")
            session.close()
            await http_client.aclose()
            return

        # Execute the API call
        result = await handle_action(http_client, parsed)
        await http_client.aclose()

        session.stream(result)
        session.close()

    except Exception as e:
        logger.exception("Error processing message")
        session.error("Something went wrong.", exception=e)


app, orca = create_agent_app(
    process_message_func=process_message,
    title="Restaurant Provider Agent",
    description="Restaurant reservation API provider agent — search tables, book, cancel, list reservations",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
