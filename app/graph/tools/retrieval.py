from typing import List

from langchain.tools import tool

from app.graph.state import AgentState
from app.rag import get_retriever
from app.logger import setup_logger


logger = setup_logger().bind(name="GRAPH.TOOL.RETRIEVER")


@tool
def retrieve_context(
    user_input: str,
    persona: str,
) -> List[str]:
    """
    This tool performs read-only retrieval over the persistent vector store
    to fetch historically grounded context relevant to the active character
    (persona) and the user's query.

    Intended Usage:
    Invoke this tool ONLY when the model requires factual or canonical recall
    about the fictional world, including but not limited to:
      - Past episodes or episode-specific events
      - Character history, relationships, or behavioral patterns
      - Attribution of dialogue ("who said what")
      - Explanations of why an event occurred in prior canon

    Do NOT use this tool for:
      - Casual conversation or improvisation
      - Purely creative or hypothetical responses
      - Emotional reactions or stylistic flavor
      - Information already present in short-term state

    Inputs:
      1. user_input (str):
        The natural-language query requiring long-term memory recall.
      2. persona (str):
        The active character identity used to scope and bias retrieval.

    Behavior:
      - Executes similarity search with persona-aware reranking
      - Returns a small, high-precision set of memory chunks
      - Produces no side effects and does not mutate agent state

    Returns:
      List[str]:
        Canonical memory excerpts to be injected into downstream reasoning.
    """
    logger.info(f"Tool called | retrieve_context | persona={persona}")

    retriever = get_retriever()

    contexts = retriever.retrieve(
        query=user_input,
        active_character=persona,
        k=5,
    )
    logger.info("first chunk", contexts)
    logger.success(f"Tool result | retrieved={len(contexts)} chunks")

    return contexts
