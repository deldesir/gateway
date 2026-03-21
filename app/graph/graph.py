from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.graph.state import AgentState
from app.graph.nodes import (
    conversation_node,
    retrieved_context_summary_node,
)
from app.graph.tools.registry import ToolRegistry


def build_graph(checkpointer=None):
    """Build and compile the LangGraph agent.

    Graph topology:
      START → conversation_node
                ↓ (tools_condition)
              tool_node  ← universal: ALL registered tools (talkprep + retrieval + konex)
                ↓
              summarize_context_node  (only relevant if retrieve_context ran)
                ↓
              conversation_node (loop)
              ↓ (END)

    The universal ToolNode handles any LangChain tool call the LLM emits —
    whether it's a TalkPrep workflow tool (import_talk, develop_section …),
    a retrieval call, or a Konex dossier fetch.

    Note: retrieved_context_summary_node is wired after tool_node to preserve
    context summarisation for retrieval calls.  For non-retrieval tools the
    node is a lightweight no-op (state pass-through if no retrieved_chunks).
    """
    graph = StateGraph(AgentState)

    # Universal tool executor — handles ALL registered tools
    all_tools = ToolRegistry.all_tools()
    tool_node = ToolNode(all_tools)

    graph.add_node("conversation_node", conversation_node)
    graph.add_node("tool_node", tool_node)
    graph.add_node("summarize_context_node", retrieved_context_summary_node)

    graph.add_edge(START, "conversation_node")

    # Route tool calls to the universal tool_node; end otherwise
    graph.add_conditional_edges(
        "conversation_node",
        tools_condition,
        {
            "tools": "tool_node",
            END: END,
        },
    )

    # After any tool executes, optionally summarise then loop back
    graph.add_edge("tool_node", "summarize_context_node")
    graph.add_edge("summarize_context_node", "conversation_node")

    return graph.compile(checkpointer=checkpointer)
