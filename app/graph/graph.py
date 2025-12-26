from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.graph.nodes import character_node
from app.logger import setup_logger

logger = setup_logger().bind(name="GRAPH")


def build_graph(persona: str):
    """
    Builds a persona-based Office agent graph.
    One graph, one user thread, persona-isolated memory.
    """
    logger.info(f"Building graph for persona: {persona}")

    graph = StateGraph(AgentState)

    graph.add_node("persona", lambda state: character_node(state, persona))

    graph.set_entry_point("persona")
    graph.add_edge("persona", END)


    compiled = graph.compile()

    logger.success("Graph compiled")

    return compiled
