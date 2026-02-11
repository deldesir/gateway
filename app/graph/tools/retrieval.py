from typing import List, Annotated, Dict
from langgraph.prebuilt import InjectedState

from langchain.tools import tool

from app.graph.state import AgentState
from app.rag import get_retriever
from app.logger import setup_logger


logger = setup_logger().bind(name="GRAPH.TOOL.RETRIEVER")


@tool
def retrieve_context(
    user_input: str,
    state: Annotated[Dict, InjectedState],
) -> List[str]:
    """
    This tool performs read-only retrieval over the persistent vector store
    to fetch historically grounded context relevant to the active character
    (persona) and the user's query.

    Intended Usage:
    Invoke this tool ONLY when the model requires factual or canonical recall
    about the fictional world.

    Inputs:
      1. user_input (str):
        The natural-language query requiring long-term memory recall.
      2. state (dict):
        Injected AgentState containing 'persona'.

    Returns:
      List[str]:
        Canonical memory excerpts.
    """
    persona = state.get("persona", "konex-support")
    logger.info(f"Tool called | retrieve_context | persona={persona}")

    retriever = get_retriever()

    contexts = retriever.retrieve(
        query=user_input,
        active_character=persona,
        k=5,
    )
    logger.info(f"first chunk {contexts}")
    logger.success(f"Tool result | retrieved={len(contexts)} chunks")

    return contexts
