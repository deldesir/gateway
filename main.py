"""
Entry point for running the Office Agents backend in terminal mode.

This script builds the LangGraph, renders its Mermaid diagram, saves the diagram
as both Mermaid text and PNG, and executes a single agent run.
"""

from pathlib import Path
from app.logger import setup_logger

from langchain_core.messages import HumanMessage, AIMessage

from app.graph.graph import build_graph

logger = setup_logger().bind(name="LLM")


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
    """
    Run the Office Agents system in terminal mode.
    """
    logger.info("Starting Office Agents backend (terminal mode)")

    persona = input("Choose character (michael / dwight / jim): ").strip().lower()
    user_input = input("Enter your message: ").strip()

    logger.info("Persona selected: {}", persona)
    logger.info("User input: {}", user_input)

    graph = build_graph()
    render_graph(graph)

    state = {
        "persona": persona,
        "messages": [HumanMessage(content=user_input)],
        "retrieved_context": None,
        "conversation_summary": None,
        "final_response": None,
    }

    logger.info("Invoking graph")
    final_state = graph.invoke(state)
    print("FINAL STATE IS:::", final_state)
    logger.info("Graph execution completed")

    final_message = None
    for msg in reversed(final_state.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            final_message = msg.content
            break

    if final_message is None:
        logger.error("No final AIMessage found in state.messages")
        logger.debug("Final state: {}", final_state)
        print("\n[ERROR] No response generated.")
        return

    logger.success("Final response generated")

    print(f"\n{persona} says:\n")
    print(final_message)


if __name__ == "__main__":
    main()
