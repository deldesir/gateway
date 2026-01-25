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
from app.logger import setup_logger
from langchain_groq import ChatGroq

logger = setup_logger().bind(name="LLM")


@lru_cache(maxsize=1)
def _get_base_llm() -> ChatGroq:
    """
    Initialize and cache the base ChatGroq LLM client.
    """
    config = load_config()
    llm_cfg = config.llm

    logger.success(
        "ChatGroq initialized | model={} | temperature={}",
        llm_cfg.model,
        llm_cfg.temperature,
    )

    return ChatGroq(
        model=llm_cfg.model,
        temperature=llm_cfg.temperature,
        api_key=llm_cfg.api_key,
    )


def get_llm() -> ChatGroq:
    """
    Return the cached base LLM client (no tools bound).
    """
    return _get_base_llm()


def get_llm_with_tools(tools: List[Any]) -> ChatGroq:
    """
    Return the cached LLM client with tools bound.
    """
    llm = _get_base_llm()
    return llm.bind_tools(tools)


@lru_cache(maxsize=1)
def get_embedder() -> EmbeddingClient:
    """
    Factory method for initializing the configured embedding client.
    """

    config = load_config()
    emb_cfg = config.embeddings

    if emb_cfg.provider == "local":
        return LocalHFEmbeddingClient(model_name=emb_cfg.model)

    return LiteLLMEmbeddingClient(model=emb_cfg.model)
