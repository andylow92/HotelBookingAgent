import logging
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables

from travelneg.consumer_agent.agent import ConsumerAgent

logger = logging.getLogger(__name__)


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

        # Determine domain from variables or default to hotels
        domain = variables.get("DOMAIN") or "hotels"

        # Create the consumer agent and handle the message
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
