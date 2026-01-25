"""
Entry point for running the Office Agents backend in terminal mode.

This script builds the LangGraph, renders its Mermaid diagram, executes
a single agent run, and persists state using a custom JSON checkpointer.
"""

from pathlib import Path
from loguru import logger

from langchain_core.messages import HumanMessage, AIMessage
from app.logger import setup_logger
from app.graph.graph import build_graph
from app.memory.json_checkpointer import JsonCheckpointer

logger = setup_logger().bind(name="MAIN")


def render_graph(graph):
    """
    Render and persist the Mermaid diagram and PNG for the graph.
    """
    output_dir = Path("graph_artifacts")
    output_dir.mkdir(exist_ok=True)

    mermaid_path = output_dir / "graph.mmd"
    png_path = output_dir / "graph.png"

    mermaid_code = graph.get_graph().draw_mermaid()
    mermaid_path.write_text(mermaid_code)

    try:
        png_bytes = graph.get_graph().draw_mermaid_png()
        png_path.write_bytes(png_bytes)
    except Exception as e:
        logger.warning("Could not render Mermaid PNG: {}", e)

    logger.info("Mermaid diagram saved to {}", mermaid_path)
    logger.info("Mermaid PNG saved to {}", png_path)


def main():
    logger.info("Starting Office Agents backend (terminal mode)")

    persona = input("Choose character (michael / dwight / jim): ").strip().lower()
    user_input = input("Enter your message: ").strip()

    graph = build_graph()
    store = JsonCheckpointer("memory.json")

    thread_id = persona  # persona-scoped memory

    loaded = store.get(thread_id)
    state = (
        loaded
        if loaded
        else {
            "persona": persona,
            "messages": [],
            "retrieved_context": None,
            "conversation_summary": None,
            "final_response": None,
        }
    )

    state["messages"].append(HumanMessage(content=user_input))

    final_state = graph.invoke(state)

    store.put(thread_id, final_state)

    final_message = None
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            final_message = msg.content
            break

    print(f"\n{persona} says:\n")
    print(final_message)


if __name__ == "__main__":
    main()
