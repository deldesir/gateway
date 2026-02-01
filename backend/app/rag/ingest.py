"""
This is the main file that we run once in order to create the vector db and ingest all the chunks into it, provided we have the jsonl file for creating the vector db in the first place.
"""

from pathlib import Path
from typing import List

from tqdm import tqdm

from app.logger import setup_logger
from app.rag.chunker import iter_chunks
from app.rag.vectorstore import VectorStore
from app.llm import get_embedder


logger = setup_logger().bind(name="rag.ingest")

BATCH_SIZE = 32

VECTORSTORE_PATH = Path("data/vectorstore")


def _flush_batch(
    vectorstore: VectorStore,
    embedder,
    texts: List[str],
    metadatas: List[dict],
):
    """
    Embed a batch and persist it to the vector store.
    """
    logger.info(f"Embedding batch | size={len(texts)}")

    vectors = embedder.embed(texts)

    vectorstore.add(
        vectors=vectors,
        metadatas=metadatas,
        persist=True,
    )

    logger.success(f"Batch ingested | vectors_added={len(vectors)}")


def ingest(jsonl_path: str | Path):
    """
    Offline ingestion pipeline:
    JSONL -> Chunks -> Embeddings -> FAISS
    """
    logger.info("Starting RAG ingestion pipeline")

    embedder = get_embedder()

    vectorstore = VectorStore(
        index_path=VECTORSTORE_PATH,
        dim=384,  # MiniLM dimension (safe default)
    )

    texts: List[str] = []
    metadatas: List[dict] = []

    total_chunks = 0

    for chunk in tqdm(iter_chunks(jsonl_path), desc="Ingesting chunks"):
        texts.append(chunk.to_embedding_text())
        metadatas.append(chunk.to_vector_metadata())
        total_chunks += 1

        if len(texts) >= BATCH_SIZE:
            _flush_batch(vectorstore, embedder, texts, metadatas)
            texts.clear()
            metadatas.clear()

    # Flush remaining leftover chunks
    if texts:
        _flush_batch(vectorstore, embedder, texts, metadatas)

    logger.success(
        f"Ingestion completed | total_chunks={total_chunks} | index_size={vectorstore.index.ntotal}"
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise ValueError("Usage: python -m app.rag.ingest <path_to_jsonl>")

    ingest(sys.argv[1])
