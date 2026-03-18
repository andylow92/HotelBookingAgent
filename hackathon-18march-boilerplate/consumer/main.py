import logging
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables, ChatHistoryHelper

logger = logging.getLogger(__name__)


async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)
        # openai_key = variables.get("OPENAI_API_KEY")

        # --- Connected provider agents ---
        # Orca automatically provides the list of agents connected to yours.
        # Use this to discover available providers at runtime:
        #
        # for agent in session.available_agents:
        #     print(agent.slug, agent.name, agent.description)

        # --- Delegating to a provider agent ---
        # Send a question to a connected agent and get a response:
        #
        # response = session.ask_agent("agent-slug", "your question here")

        # --- Chat history ---
        # Access prior messages in the conversation:
        #
        # history = ChatHistoryHelper(data.chat_history)
        # recent = history.get_last_n_messages(10)

        # --- Your consumer agent logic goes here ---
        #
        # You are building a CONSUMER agent — a personal AI assistant
        # that helps a user with travel-related tasks.
        #
        # Your job:
        # 1. Use any LLM to understand what the user wants
        # 2. Delegate to the right provider agent(s) using session.ask_agent()
        # 3. Synthesize the provider's response into a friendly reply
        #
        # At demo time, your consumer will be connected to ALL provider
        # agents from every team through Orca orchestration.

        session.stream("Consumer agent is not implemented yet.")
        session.close()

    except Exception as e:
        logger.exception("Error processing message")
        session.error("Something went wrong.", exception=e)


app, orca = create_agent_app(
    process_message_func=process_message,
    title="Consumer Agent",
    description="Personal travel assistant with agent delegation",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
