import os
from pydantic import BaseModel
from typing import Literal


class LLMConfig(BaseModel):
    model: str = "gemini/gemini-2.5-flash"
    temperature: float = 0.3


class AppConfig(BaseModel):
    llm: LLMConfig


def load_config() -> AppConfig:
    """
    Loads application configuration from environment variables.

    Returns:
        AppConfig: Parsed application configuration.
    """
    return AppConfig(
        llm=LLMConfig(
            model=os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        )
    )
