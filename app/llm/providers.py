"""
LLM Provider — wraps ChatOpenAI pointed at the local LiteLLM proxy.

Replaces the deprecated langchain-litellm package with the maintained
langchain-openai approach: ChatOpenAI(base_url=..., api_key=...).
This works identically since our litellm proxy exposes an OpenAI-compatible API.
"""

import os
from typing import List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage

from app.llm.client import LLMClient
from app.logger import setup_logger

logger = setup_logger().bind(name="LLM")

_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:4000")
_API_KEY  = os.getenv("OPENAI_API_KEY", "sk-placeholder")


class LiteLLMClient(LLMClient):
    """
    ChatOpenAI-based client pointed at the local LiteLLM proxy.

    Using ChatOpenAI(base_url=...) is the recommended approach after
    langchain-litellm was deprecated upstream in 2024.
    """

    def __init__(self, model: str, temperature: float, tools: Optional[List] = None):
        self.model = model
        self.temperature = temperature
        self.tools = tools
        self._chat_model: BaseChatModel = ChatOpenAI(
            model=model,
            temperature=temperature,
            base_url=_API_BASE,
            api_key=_API_KEY,
        )
        logger.success(
            f"LLM initialized | model={model} | temp={temperature} | base={_API_BASE}"
        )

    def get_chat_model(self) -> BaseChatModel:
        return self._chat_model

    def get_chat_model_with_tools(self) -> BaseChatModel:
        if not self.tools:
            return self._chat_model
        return self._chat_model.bind_tools(self.tools)

    def generate(self, messages: List[BaseMessage]) -> AIMessage:
        if not messages:
            raise ValueError("Messages must not be empty")

        logger.info("Sending prompt via ChatOpenAI → LiteLLM proxy")
        chat_model = (
            self.get_chat_model_with_tools() if self.tools else self.get_chat_model()
        )

        try:
            ai_message: AIMessage = chat_model.invoke(messages)
        except Exception as e:
            logger.error(
                "LLM generation failed",
                error=str(e),
                model=self.model,
                message_count=len(messages),
            )
            raise

        logger.success("LLM response received")
        if getattr(ai_message, "tool_calls", None):
            logger.info(
                "LLM emitted tool calls",
                tools=[tc["name"] for tc in ai_message.tool_calls],
            )
        return ai_message
