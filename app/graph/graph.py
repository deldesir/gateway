from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from app.graph.state import AgentState
from app.graph.nodes import character_node
from app.graph.tools.retrieval import retrieve_context
from app.logger import setup_logger

logger = setup_logger().bind(name="GRAPH")


def build_graph(character: str):
    """
    Builds a character-based Office agent graph.
    One graph, one user thread, character-isolated memory.
    """
    logger.info(f"Building graph for character: {character}")

    graph = StateGraph(AgentState)

    graph.add_node(
        "character",
        lambda state: character_node(state, character),
    )

    tool_node = ToolNode(tools=[retrieve_context])
    graph.add_node("tools", tool_node)

    graph.set_entry_point("character")

    graph.add_conditional_edges(
        "character",
        tools_condition,
    )

    graph.add_edge("tools", "character")

    compiled = graph.compile()

    logger.success("Graph compiled")

    return compiled
