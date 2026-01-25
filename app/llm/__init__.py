"""
Learnt a new thing called lru_cache, here we implement this so that every other time we call the get_llm method, it returns the cached version of the LLM client instead of creating a new one every time. i mean i already knew about caching but this is the first time i actually got to use it in a real project, hehe.
"""

from functools import lru_cache
from app.config import load_config
from app.llm.client import LLMClient
from langchain_litellm import ChatLiteLLM
from app.llm.providers import LiteLLMClient
from app.llm.embedding_client import EmbeddingClient
from app.llm.embedder import LiteLLMEmbeddingClient, LocalHFEmbeddingClient
from typing import List, Any, Optional


def _get_base_llm() -> ChatLiteLLM:
    config = load_config()
    llm_cfg = config.llm

    return LiteLLMClient(
        model=llm_cfg.model,
        temperature=llm_cfg.temperature,
    )


def get_llm() -> ChatLiteLLM:
    """
    Returns base LLM client (no tools bound).
    """
    return _get_base_llm()


def get_llm_with_tools(tools: List[Any]) -> ChatLiteLLM:
    """
    Returns LLM client with tools configured.
    """
    llm = _get_base_llm()
    return llm.bind_tools(tools=tools)


def get_embedder() -> EmbeddingClient:
    """
    Factory method for initializing the configured embedding client.
    """

    config = load_config()
    emb_cfg = config.embeddings

    if emb_cfg.provider == "local":
        return LocalHFEmbeddingClient(model_name=emb_cfg.model)

    return LiteLLMEmbeddingClient(model=emb_cfg.model)
