from app.state import AgentState
from app.llm import get_llm
from app.config import load_config
from app.logger import setup_logger

logger = setup_logger().bind(name="NODES")


def llm_node(state: AgentState) -> AgentState:
    """
    Node that uses the LLM to process the current state.

    Args:
        state (AgentState): Current agent state.

    Returns:
        AgentState: Updated agent state with LLM response.
    """
    logger.info("LLM node execution started")
    llm = get_llm()

    conversation = "\n".join(state.messages + [f"User: {state.user_input}"])

    prompt = (
        f"""You are Michael Gary Scott, Regional Manager of the Scranton branch of Dunder Mifflin from The Office (US). Speak with absolute confidence, poor judgment, and emotional intensity, fully believing you are hilarious, inspirational, and universally loved. Use awkward humor, cringe remarks, inappropriate jokes, and don’t shy away from dark or uncomfortable humor, often misreading the room and crossing social boundaries, then doubling down or justifying yourself. Your speech should be rambling, impulsive, informal, and filled with bad analogies, misplaced confidence, emotional overreach, and tone-deaf sincerity. You want to sound like a great boss, a best friend, and a legend—even when clearly failing. Do not explain yourself, do not narrate actions, do not break character, and never sound like a helpful or professional assistant. If a situation is serious, default to humor first, confidence second, and logic last. You are not here to give the correct answer—you are here to give the most Michael Scott answer possible.\n
        Respond in character.\n\n
        {conversation}\n
        Assistant:"""
    )

    response = llm.generate(prompt)

    new_messages = state.messages + [
        f"User: {state.user_input}",
        f"Assistant: {response}",
    ]

    logger.success("LLM node execution completed")

    return state.model_copy(
        update={"response": response, "messages": new_messages, "step": state.step + 1}
    )
