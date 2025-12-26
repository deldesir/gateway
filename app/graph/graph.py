import sqlite3
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from app.graph.state import AgentState
from app.graph.nodes import character_node
from app.logger import setup_logger

conn = sqlite3.connect("office_agents.db", check_same_thread=False)
logger = setup_logger().bind(name="GRAPH")


def build_graph(character: str):
    """
    Builds a persona-based Office agent graph.
    One graph, one user thread, character-isolated memory.
    """
    logger.info(f"Building graph for character: {character}")

    graph = StateGraph(AgentState)

    graph.add_node("character", lambda state: character_node(state, character))

    graph.set_entry_point("character")
    graph.add_edge("character", END)

    checkpointer = SqliteSaver(conn)

    compiled = graph.compile(checkpointer=checkpointer)

    logger.success("Graph compiled with SQLite checkpointing")

    return compiled
