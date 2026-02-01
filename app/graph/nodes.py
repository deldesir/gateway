"""
Graph node implementations for the agent system.

Each node is responsible for executing a single chain and writing the resulting
artifact back into the agent state. Nodes do not contain control flow logic or
branching decisions, which are handled exclusively by graph edges.
"""

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


def conversation_node(state):
    """
    Execute the conversation chain and update the assistant response state.
    """
    persona = state["persona"]
    messages = state.get("messages", [])

    user_input = state.get("user_input")
    if user_input:
        messages = messages + [HumanMessage(content=user_input)]
        state["user_input"] = ""

    chain = ConversationChain(persona=persona).build()
    ai_message: AIMessage = chain.invoke({"messages": messages})

    final_response = state.get("final_response")
    if ai_message.content:
        final_response = ai_message.content

    return {
        **state,
        "messages": messages + [ai_message],
        "final_response": final_response,
    }


def retrieved_context_summary_node(state: AgentState) -> AgentState:
    """
    Summarize raw retrieved chunks into a canonical factual context.
    """
    retrieved_chunks = state.get("retrieved_chunks", [])

    print("retrieved_chunks:::", retrieved_chunks)

    joined_context = "\n\n".join(retrieved_chunks)

    chain = RetrievedContextSummaryChain(retrieved_chunks=joined_context).build()

    ai_message: AIMessage = chain.invoke({})

    return {
        **state,
        "context_summary": ai_message.content,
    }


def final_response_node(state):
    """
    Terminal node that optionally summarizes the conversation history and
    always produces the final in-character response.
    """
    persona = state["persona"]
    messages = state.get("messages", [])

    conversation_summary = state.get("conversation_summary")
    logger.debug("Retrieved context: {}", state.get("retrieved_context"))
    if len(messages) > 20:
        summary_chain = ConversationSummaryChain(persona=persona).build()
        summary_message = summary_chain.invoke({"messages": messages[-20:]})

        conversation_summary = summary_message.content
        messages = messages[:-20]

    response_chain = FinalResponseChain(
        persona=persona,
        retrieved_context=state.get("retrieved_context"),
        conversation_summary=conversation_summary,
    ).build()

    ai_message: AIMessage = response_chain.invoke({"messages": messages})

    return {
        **state,
        "messages": messages + [ai_message],
        "conversation_summary": conversation_summary,
        "final_response": ai_message.content,
    }
