"""
This is the file where we would define all the LLM providers, and if it wasn't for LiteLLM, we would have needed to define a new class for every LLM provider we wanted to support. But since LiteLLM supports multiple providers via model strings, we can just have one class that uses LiteLLM to connect to any provider we want.

And here as we can see, the LiteLLM class also uses the generate method that we abstracted in the LLMClient interface.
"""

from litellm import completion
from app.llm.client import LLMClient
from app.logger import setup_logger
from typing import List, Dict, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_community.chat_models import ChatLiteLLM
from langchain_core.messages import BaseMessage, AIMessage

Message = Dict[str, str]

logger = setup_logger().bind(name="LLM")


class LiteLLMClient(LLMClient):
    """
    LiteLLM-based client supporting multiple providers via model strings.
    """

    def __init__(self, model: str, temperature: float, tools: Optional[List] = None):
        """
        Initializes the LiteLLM client.

        Args:
            model (str): Model identifier (e.g. gemini/gemini-2.5-flash).
            temperature (float): Sampling temperature.
        """
        self.model = model
        self.temperature = temperature
        self.tools = tools
        self._chat_model: BaseChatModel = ChatLiteLLM(
            model=self.model,
            temperature=self.temperature,
        )

        logger.success(f"LiteLLM initialized | model={model} | temp={temperature}")

    def get_chat_model(self) -> BaseChatModel:
        """
        Returns the underlying chat model (unbound).

        """
        return self._chat_model

    def get_chat_model_with_tools(self) -> BaseChatModel:
        """
        Return a chat model instance with the provided tools bound for tool calling.

        This method binds the given list of LangChain-compatible tools to the
        underlying chat model, enabling the model to emit structured tool calls
        during inference. The returned model can be safely used inside LangGraph
        nodes where tool invocation is controlled via `tools_condition` and
        `ToolNode`.

        Tool binding is performed at call time (not at model initialization),
        allowing different graphs or personas to attach different tool sets
        without creating circular dependencies or new model instances.

        Args:
            tools (List): A list of LangChain tool definitions (e.g., functions
                decorated with `@tool`) to be made available to the chat model.

        Returns:
            BaseChatModel: A chat model instance with the specified tools bound
                and ready for tool-aware invocation.
        """
        if not self.tools:
            return self._chat_model
        return self._chat_model.bind_tools(self.tools)

    def generate(self, messages: List[BaseMessage]) -> AIMessage:
        """
        Generates a response using ChatLiteLLM.

        Args:
            messages (List[BaseMessage]): LangChain chat messages.

        Returns:
            AIMessage: Model response (may include tool_calls).
        """
        if not messages:
            logger.warning("generate() called with empty messages list")
            raise ValueError("Messages must not be empty")

        logger.info("Sending prompt via ChatLiteLLM")

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
