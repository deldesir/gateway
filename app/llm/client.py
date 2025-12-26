"""This is just an abstract class for defining all the LLM clients, it means that if we want to add a new LLM client, we define it inside the providers.py file and implement this interface, and this means that every provider needs to have a generate method that takes in a prompt and returns a string response."""

from abc import ABC, abstractmethod
from typing import List, Dict

Message = Dict[str, str]   

class LLMClient(ABC):
    """
    Abstract interface for all LLM clients.
    """

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
