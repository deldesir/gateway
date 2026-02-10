from typing import Optional, Dict, Any
from langchain_core.runnables import Runnable

from app.llm import get_llm_summarizer, get_llm
from app.graph.prompts import (
    ConversationPrompt,
    ConversationSummaryPrompt,
    ExtendConversationSummaryPrompt,
    RetrievedContextSummaryPrompt,
    FinalResponsePrompt,
)
from app.graph.tools import retrieve_context, fetch_dossier, start_flow

class ConversationChain:
    """
    Chain used for the initial conversation turn.

    This is the only chain where tool usage is permitted. It is executed exactly
    once per graph run.
    """

    def __init__(
        self,
        persona_vars: Dict[str, Any],
        trust_score: int = 50,
        mood: str = "Neutral",
        dossier: Optional[dict] = None,
    ):
        self.persona_vars = persona_vars
        self.trust_score = trust_score
        self.mood = mood
        self.dossier = dossier or {}

    def build(self) -> Runnable:
        tools = [retrieve_context, fetch_dossier, start_flow]
        model = get_llm().bind_tools(tools=tools)
        prompt = ConversationPrompt(
            self.persona_vars,
            trust_score=self.trust_score,
            mood=self.mood,
            dossier=self.dossier,
        ).build()

        return prompt | model




class ConversationSummaryChain:
    """
    Chain used to extend an existing conversation summary.
    """

    def __init__(self, persona_vars: Dict[str, Any], summary: Optional[str] = None):
        self.persona_vars = persona_vars
        self.summary = summary or ""

    def build(self) -> Runnable:
        """
        Build the runnable extend-summary chain.
        """
        model = get_llm()
        if len(self.summary) > 0:
            prompt = ExtendConversationSummaryPrompt(
                persona_vars=self.persona_vars,
                summary=self.summary,
            ).build()
        else:
            prompt = ConversationSummaryPrompt(persona_vars=self.persona_vars).build()
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
        persona_vars: Dict[str, Any],
        retrieved_context: Optional[str] = None,
        conversation_summary: Optional[str] = None,
    ):
        self.persona_vars = persona_vars
        self.retrieved_context = retrieved_context
        self.conversation_summary = conversation_summary

    def build(self) -> Runnable:
        """
        Build the runnable final response chain.
        """
        model = get_llm()
        prompt = FinalResponsePrompt(
            persona_vars=self.persona_vars,
            retrieved_context=self.retrieved_context,
            conversation_summary=self.conversation_summary,
        ).build()
        return prompt | model
