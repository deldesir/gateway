from typing import Optional
from langchain_core.runnables import Runnable

from app.llm import get_llm_summarizer, get_llm
from app.graph.prompts import (
    ConversationPrompt,
    ConversationSummaryPrompt,
    ExtendConversationSummaryPrompt,
    RetrievedContextSummaryPrompt,
    FinalResponsePrompt,
)
from app.graph.tools.retrieval import retrieve_context


class ConversationChain:
    """
    Chain used for the initial conversation turn.

    This is the only chain where tool usage is permitted. It is executed exactly
    once per graph run.
    """

    def __init__(self, persona: str):
        self.persona = persona

    def build(self) -> Runnable:
        model = get_llm().bind_tools(tools=[retrieve_context])
        prompt = ConversationPrompt(self.persona).build()

        return prompt | model




class ConversationSummaryChain:
    """
    Chain used to extend an existing conversation summary.
    """

    def __init__(self, persona: str, summary: Optional[str] = None):
        self.persona = persona
        self.summary = summary or ""

    def build(self) -> Runnable:
        """
        Build the runnable extend-summary chain.
        """
        model = get_llm()
        if len(self.summary) > 0:
            prompt = ExtendConversationSummaryPrompt(
                persona=self.persona,
                summary=self.summary,
            ).build()
        else:
            prompt = ConversationSummaryPrompt(persona=self.persona)
        return prompt | model


class RetrievedContextSummaryChain:
    """
    Chain used to summarize retrieved vector database context.
    """

    def __init__(self, retrieved_chunks: str):
        self.retrieved_chunks = retrieved_chunks

    def build(self) -> Runnable:
        """
        Build the runnable retrieved-context summary chain.
        """
        model = get_llm_summarizer()
        prompt = RetrievedContextSummaryPrompt(
            retrieved_context=self.retrieved_chunks
        ).build()
        return prompt | model


class FinalResponseChain:
    """
    Chain used to generate the final in-character response.
    """

    def __init__(
        self,
        persona: str,
        retrieved_context: Optional[str] = None,
        conversation_summary: Optional[str] = None,
    ):
        self.persona = persona
        self.retrieved_context = retrieved_context
        self.conversation_summary = conversation_summary

    def build(self) -> Runnable:
        """
        Build the runnable final response chain.
        """
        model = get_llm()
        prompt = FinalResponsePrompt(
            persona=self.persona,
            retrieved_context=self.retrieved_context,
            conversation_summary=self.conversation_summary,
        ).build()
        return prompt | model
