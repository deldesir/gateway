"""
This is the file where we would define all the LLM providers, and if it wasn't for LiteLLM, we would have needed to define a new class for every LLM provider we wanted to support. But since LiteLLM supports multiple providers via model strings, we can just have one class that uses LiteLLM to connect to any provider we want.

And here as we can see, the LiteLLM class also uses the generate method that we abstracted in the LLMClient interface.
"""

from litellm import completion
from app.llm.client import LLMClient
from app.logger import setup_logger

logger = setup_logger().bind(name="LLM")


class LiteLLMClient(LLMClient):
    """
    LiteLLM-based client supporting multiple providers via model strings.
    """

    def __init__(self, model: str, temperature: float):
        """
        Initializes the LiteLLM client.

        Args:
            model (str): Model identifier (e.g. gemini/gemini-2.5-flash).
            temperature (float): Sampling temperature.
        """
        self.model = model
        self.temperature = temperature

        logger.success(f"LiteLLM initialized | model={model} | temp={temperature}")

    def generate(self, prompt: str) -> str:
        """
        Generates text using LiteLLM.

        Args:
            prompt (str): Input prompt.

        Returns:
            str: Generated response text.
        """
        logger.info("Sending prompt via LiteLLM")

        response = completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )

        text = response.choices[0].message.content.strip()

        logger.success("LiteLLM response received")

        return text
