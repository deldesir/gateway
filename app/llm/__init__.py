"""
Learnt a new thing called lru_cache, here we implement this so that every other time we call the get_llm method, it returns the cached version of the LLM client instead of creating a new one every time. i mean i already knew about caching but this is the first time i actually got to use it in a real project, hehe.
"""

from functools import lru_cache
from app.config import load_config
from app.llm.client import LLMClient
from app.llm.providers import LiteLLMClient


@lru_cache
def get_llm() -> LLMClient:
    """
    Factory method for initializing the configured LLM client.

    Returns:
        LLMClient: Instantiated LLM client.
    """
    config = load_config()
    llm_cfg = config.llm

    return LiteLLMClient(
        model=llm_cfg.model,
        temperature=llm_cfg.temperature,
    )
