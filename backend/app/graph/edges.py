from typing_extensions import Literal
from langgraph.graph import END

from app.graph.state import AgentState


def should_summarize_conversation(
    state: AgentState,
) -> Literal["summarize_conversation_node", "__end__", "final_response_node"]:
    messages = state.get("messages", [])

    if len(messages) > 20:
        return "summarize_conversation_node"

    return "final_response_node"
