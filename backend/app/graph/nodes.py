"""
Graph node implementations for the agent system.

Each node is responsible for executing a single chain and writing the resulting
artifact back into the agent state. Nodes do not contain control flow logic or
branching decisions, which are handled exclusively by graph edges.
"""

from typing import Dict, Any
from langchain_core.runnables import RunnableConfig
from app.logger import setup_logger
from app.graph.state import AgentState
from langchain_core.messages import AIMessage
from app.graph.chains import (
    ConversationChain,
    ConversationSummaryChain,
    RetrievedContextSummaryChain,
    FinalResponseChain,
)
from langgraph.prebuilt import ToolNode
from app.graph.tools.retrieval import retrieve_context

logger = setup_logger().bind(name="NODES")
retriever_node = ToolNode([retrieve_context])


from langchain_core.messages import AIMessage, HumanMessage
from app.graph.chains import ConversationChain


from app.graph.persona_logic import calculate_trust, determine_mood

from app.graph.prompts import PersonaPromptRegistry

async def conversation_node(
    state: Dict[str, Any],
    config: RunnableConfig,
) -> Dict[str, Any]:
    """
    Execute the primary conversation chain and stream assistant output.
    """
    persona_id = state["persona"]
    messages = state.get("messages", [])
    
    # Persona Engine: Load State
    trust_score = state.get("trust_score", 50)
    current_mood = state.get("mood", "Neutral")
    dossier = state.get("dossier", {})

    user_input = state.get("user_input")
    if user_input:
        # Deduplication: routes.py often seeds the state with the message.
        # Only append if it's not already the last message.
        if not messages or messages[-1].content != user_input:
            messages = messages + [HumanMessage(content=user_input)]
        state["user_input"] = None
        
        # Persona Engine: Update State based on input
        trust_score = calculate_trust(trust_score, user_input)
        current_mood = determine_mood(trust_score, current_mood)

    # Fetch Persona Async
    persona_vars = await PersonaPromptRegistry.get_async(persona_id)

    chain = ConversationChain(
        persona_vars=persona_vars,
        trust_score=trust_score,
        mood=current_mood,
        dossier=dossier,
    ).build()

    response = await chain.ainvoke(
        {"messages": messages},
        config,
    )

    return {
        "messages": response,
        "final_response": response.content,
        "trust_score": trust_score,
        "mood": current_mood,
    }


def retrieved_context_summary_node(state: AgentState) -> AgentState:
    """
    Summarize raw retrieved chunks into a canonical factual context.
    """
    retrieved_chunks = state.get("retrieved_chunks", [])

    joined_context = "\n\n".join(retrieved_chunks)

    chain = RetrievedContextSummaryChain(retrieved_chunks=joined_context).build()

    ai_message: AIMessage = chain.invoke({})

    return {
        **state,
        "context_summary": ai_message.content,
    }


async def final_response_node(state):
    """
    Terminal node that optionally summarizes the conversation history and
    always produces the final in-character response.
    """
    persona_id = state["persona"]
    messages = state.get("messages", [])

    # Fetch Persona Async
    persona_vars = await PersonaPromptRegistry.get_async(persona_id)

    conversation_summary = state.get("conversation_summary")
    logger.debug("Retrieved context: {}", state.get("retrieved_context"))
    if len(messages) > 20:
        summary_chain = ConversationSummaryChain(persona_vars=persona_vars).build()
        summary_message = await summary_chain.ainvoke({"messages": messages[-20:]})

        conversation_summary = summary_message.content
        messages = messages[:-20]

    response_chain = FinalResponseChain(
        persona_vars=persona_vars,
        retrieved_context=state.get("retrieved_context"),
        conversation_summary=conversation_summary,
    ).build()

    ai_message: AIMessage = await response_chain.ainvoke({"messages": messages})

    return {
        **state,
        "messages": messages + [ai_message],
        "conversation_summary": conversation_summary,
        "final_response": ai_message.content,
    }
