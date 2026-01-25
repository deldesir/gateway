"""
Prompt definitions and factories for the agent system.

This module centralizes all prompt construction logic using explicit prompt
classes, following the PhiloAgents architecture. Prompts are treated as
first-class objects to support observability, experimentation, and monitoring.
"""

from typing import Optional
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


class PersonaPromptRegistry:
    """
    Registry for persona-specific attributes used to construct character cards.
    """

    REGISTRY = {
        "jim": {
            "persona_name": "Jim Halpert",
            "persona_personality": "Dry, sarcastic, understated, clever",
            "persona_style": "Casual, ironic, minimalistic",
        },
        "michael": {
            "persona_name": "Michael Scott",
            "persona_personality": "Emotional, inappropriate, overconfident",
            "persona_style": "Overly enthusiastic, insecure, comedic",
        },
        "dwight": {
            "persona_name": "Dwight Schrute",
            "persona_personality": "Intense, literal, authoritarian",
            "persona_style": "Formal, aggressive, rule-obsessed",
        },
    }

    @classmethod
    def get(cls, persona: str) -> dict:
        """
        Retrieve persona attributes for prompt rendering.
        """
        return cls.REGISTRY[persona]


class SystemPrompts:
    """
    Collection of system prompt templates following the PhiloAgents style.
    """

    CHARACTER_CARD = """
        You are {{persona_name}} from *The Office*. You are having a normal, in-character
        conversation with someone, just like you would on the show. Speak naturally,
        keep your sentences short, and sound exactly like the character does on screen.

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

    def __init__(self, persona: str, summary: Optional[str] = None):
        self.persona = persona
        self.summary = summary or ""

    def build(self) -> ChatPromptTemplate:
        """
        Construct the ChatPromptTemplate for the conversation node.
        """
        persona_vars = PersonaPromptRegistry.get(self.persona)

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
                **persona_vars,
                "summary": self.summary,
            },
        )


class ConversationSummaryPrompt:
    """
    Prompt used to summarize an ongoing conversation.
    """

    def __init__(self, persona: str):
        self.persona = persona

    def build(self) -> ChatPromptTemplate:
        """
        Construct the ChatPromptTemplate for conversation summarization.
        """
        persona_vars = PersonaPromptRegistry.get(self.persona)

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
                "persona_name": persona_vars["persona_name"],
            },
        )


class ExtendConversationSummaryPrompt:
    """
    Prompt used to extend an existing conversation summary.
    """

    def __init__(self, persona: str, summary: str):
        self.persona = persona
        self.summary = summary

    def build(self) -> ChatPromptTemplate:
        """
        Construct the ChatPromptTemplate for extending a conversation summary.
        """
        persona_vars = PersonaPromptRegistry.get(self.persona)

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
                "persona_name": persona_vars["persona_name"],
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
        persona: str,
        retrieved_context: Optional[str] = None,
        conversation_summary: Optional[str] = None,
    ):
        self.persona = persona
        self.retrieved_context = retrieved_context
        self.conversation_summary = conversation_summary

    def build(self) -> ChatPromptTemplate:
        """
        Construct the ChatPromptTemplate for the final response node.
        """
        persona_vars = PersonaPromptRegistry.get(self.persona)

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
                **persona_vars,
                "summary": summary + ("\n\n" + context if context else ""),
            },
        )
