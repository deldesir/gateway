from pathlib import Path
from functools import lru_cache

from app.logger import setup_logger
from app.rag.vectorstore import VectorStore
from app.rag.retriever import Retriever


from app.llm import get_embedder

logger = setup_logger().bind(name="rag.init")

VECTORSTORE_PATH = Path("data/vectorstore")
EMBEDDING_DIM = 384


@lru_cache
def get_vectorstore() -> VectorStore:
    """
    Factory function to get a validated vectorstore instance.
    """
    logger.info("Initializing vector store")

    store = VectorStore(
        index_path=VECTORSTORE_PATH,
        dim=EMBEDDING_DIM,
    )
    
    # We allow empty stores now for dynamic ingestion
    if store.index.ntotal == 0:
        logger.warning("Vector store is empty. Ready for ingestion.")

    logger.success(f"Vector store ready | vectors={store.index.ntotal}")

    return store


@lru_cache
def get_retriever() -> Retriever:
    """
    Factory function to get a retriever instance
    backed by a validated vectorstore.
    """
    logger.info("Initializing retriever")

    vectorstore = get_vectorstore()
    retriever = Retriever(vectorstore=vectorstore)

    logger.success("Retriever ready")

    return retriever
