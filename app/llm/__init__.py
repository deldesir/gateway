"""
LLM module — factories for chat and embedding clients.

Uses lru_cache for singleton semantics: each unique config combination
produces one cached instance, avoiding repeated model loads.
"""

import os
from functools import lru_cache
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import load_config
from app.llm.embedding_client import EmbeddingClient
from app.llm.embedder import LiteLLMEmbeddingClient, LocalHFEmbeddingClient
from app.logger import setup_logger

logger = setup_logger().bind(name="LLM")

_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:4000")
_API_KEY  = os.getenv("OPENAI_API_KEY", "sk-placeholder")


@lru_cache(maxsize=1)
def _get_chat_llm() -> ChatOpenAI:
    """Initialize and cache the primary chat LLM."""
    config = load_config()
    llm_cfg = config.llm
    logger.info("Initializing primary chat LLM", model=llm_cfg.model)
    return ChatOpenAI(
        model=llm_cfg.model,
        temperature=llm_cfg.temperature,
        base_url=_API_BASE,
        api_key=_API_KEY,
    )


def get_llm() -> ChatOpenAI:
    """Return the cached primary chat LLM client."""
    logger.success("ChatOpenAI initialized")
    return _get_chat_llm()


@lru_cache(maxsize=1)
def _get_summarizer_llm() -> ChatOpenAI:
    """Initialize and cache the summarization LLM."""
    config = load_config()
    llm_cfg = config.summarizer_llm
    logger.info("Initializing summarizer LLM", model=llm_cfg.model)
    return ChatOpenAI(
        model=llm_cfg.model,
        temperature=llm_cfg.temperature,
        base_url=_API_BASE,
        api_key=_API_KEY,
    )


def get_llm_summarizer() -> ChatOpenAI:
    """Return the cached summarizer LLM client."""
    logger.success("ChatOpenAI summarizer initialized")
    return _get_summarizer_llm()


@lru_cache(maxsize=1)
def get_embedder() -> EmbeddingClient:
    """Factory method for initializing the configured embedding client."""
    config = load_config()
    emb_cfg = config.embeddings

    if emb_cfg.provider == "local":
        return LocalHFEmbeddingClient(model_name=emb_cfg.model)

    return LiteLLMEmbeddingClient(model=emb_cfg.model)
