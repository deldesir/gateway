from functools import lru_cache

from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.graph.state import AgentState
from app.graph.nodes import (
    conversation_node,
    retrieved_context_summary_node,
    connector_node,
    final_response_node,
    retriever_node,
)


@lru_cache(maxsize=1)
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("conversation_node", conversation_node)
    graph.add_node("retrieve_context", retriever_node)
    graph.add_node("summarize_context_node", retrieved_context_summary_node)

    graph.add_edge(START, "conversation_node")

    graph.add_conditional_edges(
        "conversation_node",
        tools_condition,
        {
            "tools": "retrieve_context",
            END: END,
        },
    )

    graph.add_edge("retrieve_context", "summarize_context_node")
    graph.add_edge("summarize_context_node", "conversation_node")

    return graph.compile()
