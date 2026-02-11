"""
Prompt definitions and factories for the agent system.

This module centralizes all prompt construction logic using explicit prompt
classes, following the PhiloAgents architecture. Prompts are treated as
first-class objects to support observability, experimentation, and monitoring.
"""

from typing import Optional
from typing import Optional, Dict, Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from sqlmodel import select
from app.db import async_session
from app.models import Persona


class PersonaPromptRegistry:
    """
    Registry for persona-specific attributes used to construct character cards.
    """

    REGISTRY = {
        "konex-support": {
            "persona_name": "Konex Support",
            "persona_personality": "Professional, helpful, efficient, patient.",
            "persona_style": "Formal yet friendly, speaks in Haitian Creole, focuses on solutions.",
        },
        "konex-sales": {
             "persona_name": "Konex Sales",
             "persona_personality": "Energetic, persuasive, enthusiastic, proactive.",
             "persona_style": "Casual, uses emojis, speaks in Haitian Creole, focuses on upselling plans.",
        }
    }

    @classmethod
    def get(cls, persona: str) -> dict:
        """
        Retrieve persona attributes for prompt rendering (Sync - Legacy/Fallback).
        """
        return cls.REGISTRY.get(persona, cls.REGISTRY["konex-support"])

    @classmethod
    async def get_async(cls, persona: str) -> dict:
        """
        Retrieve persona attributes, checking DB first, then static registry.
        """
        # 1. Check Static Registry first (Fast path for default personas)
        if persona in cls.REGISTRY:
            return cls.REGISTRY[persona]
        
        # 2. Check Database
        async with async_session() as session:
            statement = select(Persona).where(Persona.id == persona)
            result = await session.execute(statement)
            db_persona = result.scalar_one_or_none()
            
            if db_persona:
                return {
                    "persona_name": db_persona.name,
                    "persona_personality": db_persona.personality,
                    "persona_style": db_persona.style,
                }
        
        # 3. Fallback
        return cls.REGISTRY["konex-support"]


# Valid RapidPro Flows available to the agent
FLOW_REGISTRY = {
    "Human Handoff": "uuid-human-handoff-placeholder",
    "Registration": "uuid-registration-placeholder",
    "Emergency": "uuid-emergency-placeholder",
    "Check Balance": "uuid-balance-placeholder",
}


class SystemPrompts:
    """
    Collection of system prompt templates following the PhiloAgents style.
    """

    CHARACTER_CARD = """
        You are {{persona_name}}, the official AI agent for Konex Pro.
        
        CURRENT STATE:
        - User Trust: {{trust_score}}/100
        - Your Mood: {{mood}}
        - User Dossier: {{dossier}}
        
        AVAILABLE TOOLS / FLOWS:
        The following workflows are available. If the user asks for these, use the 'start_flow' tool with the EXACT name or UUID:
        {{available_flows}}

        LANGUAGE RULES:
        1. Speak in Haitian Creole (Kreyòl).
        2. If Trust < 30: Be short, cold, professional. No emojis.
        3. If Trust > 80: Be warm, friendly, use emojis.
        4. Otherwise: Be helpful but professional.
        
        {{system_prompt_override}}

        Everything you say should reflect who you are.

        Name: {{persona_name}}
        Personality: {{persona_personality}}
        Speaking style: {{persona_style}}

        Rules you must follow at all times:

        - Never acknowledge being an AI, model, or assistant.
        - Never reference tools, systems, retrieval, or outside knowledge sources.
        - If this is your first interaction with the user, introduce yourself naturally.
        - Respond in plain text only, with no formatting, annotations, or meta comments.
        - Remain fully in character without exception.

        Conversation summary so far:

        {{summary}}

        Continue the conversation as {{persona_name}}.

    """

    SUMMARY = """
        Create a concise summary of the conversation between {{persona_name}} and the user.
        The summary should capture all relevant facts, events, relationships, and emotional
        context shared so far.
    """

    EXTEND_SUMMARY = """
        This is a summary of the conversation so far between {{persona_name}} and the user:

        {{summary}}

        Extend the summary by incorporating the new messages above. Do not repeat
        information unnecessarily.
    """

    CONTEXT_SUMMARY = """
        Your task is to summarize the following factual information into a clean,
        non-redundant summary of canonical facts. Only include information that is
        relevant and explicitly stated. Do not speculate or add new details.

        {{context}}
    """


class ConversationPrompt:
    """
    Prompt used in the initial conversation node.
    """

    def __init__(
        self,
        persona_vars: Dict[str, Any],
        summary: Optional[str] = None,
        trust_score: int = 50,
        mood: str = "Neutral",
        dossier: Optional[dict] = None,
    ):
        self.persona_vars = persona_vars
        self.summary = summary or ""
        self.trust_score = trust_score
        self.mood = mood
        self.dossier = dossier or {}

    def build(self) -> ChatPromptTemplate:
        """
        Construct the ChatPromptTemplate for the conversation node.
        """
        return ChatPromptTemplate(
            [
                (
                    "system",
                    SystemPrompts.CHARACTER_CARD,
                ),
                MessagesPlaceholder(variable_name="messages"),
            ],
            template_format="jinja2",
            partial_variables={
                **self.persona_vars,
                "system_prompt_override": "", # Hook for future overrides
                "summary": self.summary,
                "trust_score": self.trust_score,
                "mood": self.mood,
                "dossier": str(self.dossier),
                "available_flows": "\n".join([f"- {name}: {uuid}" for name, uuid in FLOW_REGISTRY.items()]),
            },
        )


class ConversationSummaryPrompt:
    """
    Prompt used to summarize an ongoing conversation.
    """

    def __init__(self, persona_vars: Dict[str, Any]):
        self.persona_vars = persona_vars

    def build(self) -> ChatPromptTemplate:
        """
        Construct the ChatPromptTemplate for conversation summarization.
        """
        return ChatPromptTemplate(
            [
                (
                    "system",
                    SystemPrompts.SUMMARY,
                ),
                MessagesPlaceholder(variable_name="messages"),
            ],
            template_format="jinja2",
            partial_variables={
                "persona_name": self.persona_vars["persona_name"],
            },
        )


class ExtendConversationSummaryPrompt:
    """
    Prompt used to extend an existing conversation summary.
    """

    def __init__(self, persona_vars: Dict[str, Any], summary: str):
        self.persona_vars = persona_vars
        self.summary = summary

    def build(self) -> ChatPromptTemplate:
        """
        Construct the ChatPromptTemplate for extending a conversation summary.
        """
        return ChatPromptTemplate(
            [
                (
                    "system",
                    SystemPrompts.EXTEND_SUMMARY,
                ),
                MessagesPlaceholder(variable_name="messages"),
            ],
            template_format="jinja2",
            partial_variables={
                "persona_name": self.persona_vars["persona_name"],
                "summary": self.summary,
            },
        )


class RetrievedContextSummaryPrompt:
    """
    Prompt used to summarize retrieved vector database context.
    """

    def __init__(self, retrieved_context: Optional[str] = None):
        self.retrieved_context = retrieved_context

    def build(self) -> ChatPromptTemplate:
        """
        Construct the ChatPromptTemplate for retrieved context summarization.
        """
        return ChatPromptTemplate(
            [
                ("system", SystemPrompts.CONTEXT_SUMMARY),
            ],
            template_format="jinja2",
            partial_variables={
                "context": self.retrieved_context,
            },
        )


class FinalResponsePrompt:
    """
    Prompt used to generate the final in-character response.
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

    def build(self) -> ChatPromptTemplate:
        """
        Construct the ChatPromptTemplate for the final response node.
        """
        summary = self.conversation_summary or ""
        context = self.retrieved_context or ""

        return ChatPromptTemplate(
            [
                (
                    "system",
                    SystemPrompts.CHARACTER_CARD,
                ),
                MessagesPlaceholder(variable_name="messages"),
            ],
            template_format="jinja2",
            partial_variables={
                **self.persona_vars,
                "system_prompt_override": "",
                "summary": summary + ("\n\n" + context if context else ""),
            },
        )
