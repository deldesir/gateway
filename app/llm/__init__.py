"""
Learnt a new thing called lru_cache, here we implement this so that every other time we call the get_llm method, it returns the cached version of the LLM client instead of creating a new one every time. i mean i already knew about caching but this is the first time i actually got to use it in a real project, hehe.
"""

from functools import lru_cache
from app.config import load_config
from app.llm.embedding_client import EmbeddingClient
from app.llm.embedder import LiteLLMEmbeddingClient, LocalHFEmbeddingClient
from typing import List, Any, Optional
from app.logger import setup_logger
from langchain_groq import ChatGroq

logger = setup_logger().bind(name="LLM")


@lru_cache(maxsize=1)
def _get_chat_llm() -> ChatGroq:
    """
    Initialize and cache the primary chat LLM.
    """
    config = load_config()
    llm_cfg = config.llm

    logger.info("Initializing primary chat LLM", model=llm_cfg.model)

    return ChatGroq(
        model=llm_cfg.model,
        temperature=llm_cfg.temperature,
        api_key=llm_cfg.api_key,
        streaming=True,
    )


def get_llm() -> ChatGroq:
    """
    Return the cached primary chat LLM client.
    """
    logger.success(
        "ChatGroq initialized | model= base_model",
    )
    return _get_chat_llm()


@lru_cache(maxsize=1)
def _get_summarizer_llm() -> ChatGroq:
    """
    Initialize and cache the summarization LLM.
    """
    config = load_config()
    llm_cfg = config.summarizer_llm

    logger.info("Initializing summarizer LLM", model=llm_cfg.model)

    return ChatGroq(
        model=llm_cfg.model,
        temperature=llm_cfg.temperature,
        api_key=llm_cfg.api_key,
    )


def get_llm_summarizer() -> ChatGroq:
    """
    Return the cached summarizer LLM client.
    """
    logger.success(
        "ChatGroq initialized | model= summarizer_model",
    )
    return _get_summarizer_llm()


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
