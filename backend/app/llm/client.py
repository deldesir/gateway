"""This is just an abstract class for defining all the LLM clients, it means that if we want to add a new LLM client, we define it inside the providers.py file and implement this interface, and this means that every provider needs to have a generate method that takes in a prompt and returns a string response."""

from abc import ABC, abstractmethod
from langchain_core.language_models.chat_models import BaseChatModel
from typing import List, Dict, Optional

Message = Dict[str, str]


class LLMClient(ABC):
    """
    Abstract interface for all LLM clients.
    """

    @abstractmethod
    def get_chat_model(self) -> BaseChatModel:
        """
        Returns the LLM client model without any tools binded to it.

        :param self: Description
        :return: Description
        :rtype: BaseChatModel
        """
        pass

    @abstractmethod
    def get_chat_model_with_tools(self, tools: Optional[List] = None):
        pass

    @abstractmethod
    def generate(self, messages: List[Message]) -> str:
        """
        Generates a response from the LLM.

        Args:
            messages (List[Message]): Role-based chat messages.

        Returns:
            str: Generated text.
        """
        pass
