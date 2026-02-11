from functools import lru_cache
from typing import List

from litellm import embedding
from sentence_transformers import SentenceTransformer

from app.config import load_config
from app.logger import setup_logger
from app.llm.embedding_client import EmbeddingClient


logger = setup_logger().bind(name="LLM.Embedder")


class LiteLLMEmbeddingClient(EmbeddingClient):
    """
    Remote embedding client powered by LiteLLM.
    """

    def __init__(self, model: str):
        self.model = model
        logger.success(f"Remote embedding model initialized | model={model}")

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        logger.info(f"Generating remote embeddings | batch_size={len(texts)}")

        try:
            response = embedding(
                model=self.model,
                input=texts,
            )
        except Exception as e:
            logger.error("Remote embedding failed", error=str(e))
            raise

        vectors = [item["embedding"] for item in response["data"]]

        if len(vectors) != len(texts):
            raise RuntimeError("Embedding count mismatch")

        logger.success("Remote embeddings generated")
        return vectors


class LocalHFEmbeddingClient(EmbeddingClient):
    """
    Local embedding client using SentenceTransformers.
    """

    def __init__(self, model_name: str):
        logger.info(f"Loading local embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        logger.success("Local embedding model loaded")

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        logger.info(f"Generating local embeddings | batch_size={len(texts)}")

        vectors = self.model.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        logger.success("Local embeddings generated")
        return vectors.tolist()
