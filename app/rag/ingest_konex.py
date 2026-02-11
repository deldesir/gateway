from pathlib import Path
from typing import List
import uuid

from app.logger import setup_logger
from app.rag.schema import Chunk
from app.rag.vectorstore import VectorStore
from app.llm import get_embedder

logger = setup_logger().bind(name="rag.ingest_konex")

VECTORSTORE_PATH = Path("data/vectorstore")
DATA_FILE = Path("data/konex_services.txt")

def ingest_konex():
    """
    Ingest Konex services text file into the vector store.
    """
    logger.info("Starting Konex RAG ingestion")

    # 1. Initialize Components
    embedder = get_embedder()
    vectorstore = VectorStore(
        index_path=VECTORSTORE_PATH,
        dim=384,  # Standard for many sentence-transformers models
    )

    # 2. Read Data
    if not DATA_FILE.exists():
        logger.error(f"Data file not found: {DATA_FILE}")
        return

    text = DATA_FILE.read_text(encoding="utf-8")
    
    # 3. Simple Chunking (by empty lines / paragraphs)
    raw_chunks = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    vectors = []
    metadatas = []
    
    logger.info(f"Found {len(raw_chunks)} chunks to ingest")

    # 4. Create Chunks & Embed
    for i, content in enumerate(raw_chunks):
        chunk_id = str(uuid.uuid4())
        
        # Create Schema-compliant Chunk
        chunk = Chunk(
            id=chunk_id,
            text=content,
            character="Konex Guide",
            character_slug="konex-guide",
            chunk_type="quote",
             # Optional fields can be omitted or explicitly None
        )
        
        # Embed
        # Note: VectorStore expects a batch, but we can do one by one or batch it.
        # Let's batch everything for this small file.
        
        # We need the vector. The existing ingest.py calls embedder.embed([text])
        # Let's assume embedder.embed takes a list of strings
        
        vectors_batch = embedder.embed([chunk.to_embedding_text()])
        vector = vectors_batch[0] # Take the first one
        
        vectors.append(vector)
        metadatas.append(chunk.to_vector_metadata())

    # 5. Persist
    if vectors:
        vectorstore.add(vectors, metadatas, persist=True)
        logger.success(f"Ingested {len(vectors)} chunks into {VECTORSTORE_PATH}")
    else:
        logger.warning("No chunks to ingest.")

if __name__ == "__main__":
    ingest_konex()
