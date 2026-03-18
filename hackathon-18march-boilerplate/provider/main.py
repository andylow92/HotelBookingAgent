import logging
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables

logger = logging.getLogger(__name__)


async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)
        # API keys are provided as Orca variables — retrieve them like this:
        # api_key = variables.get("API_KEY")
        # api_base_url = variables.get("API_BASE_URL")
        # openai_key = variables.get("OPENAI_API_KEY")

        # --- Your provider agent logic goes here ---
        #
        # You are building a PROVIDER agent for a specific travel API
        # (hotels, restaurants, events, tours, car rental, etc.).
        #
        # Your job:
        # 1. Connect to your assigned API (REST calls with authentication)
        # 2. Use any LLM (OpenAI, Anthropic, etc.) to understand incoming requests
        # 3. Map user intent to API actions (search, book, cancel, list, etc.)
        # 4. Return concise, structured results
        #
        # This agent will be called by consumer agents via Orca.
        # Keep responses short and data-rich — the consumer agent
        # will format them for the end user.

        session.stream("Provider agent is not implemented yet.")
        session.close()

    except Exception as e:
        logger.exception("Error processing message")
        session.error("Something went wrong.", exception=e)


app, orca = create_agent_app(
    process_message_func=process_message,
    title="Provider Agent",
    description="Travel API provider agent",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
