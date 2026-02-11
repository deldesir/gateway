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
    Ingest Konex services text file AND persona knowledge files into the vector store.
    """
    logger.info("Starting Konex RAG ingestion")

    # 1. Initialize Components
    embedder = get_embedder()
    vectorstore = VectorStore(
        index_path=VECTORSTORE_PATH,
        dim=384,  # Standard for many sentence-transformers models
    )

    vectors = []
    metadatas = []

    # Helper function to process a file
    def process_file(file_path: Path, character: str, slug: str):
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return

        text = file_path.read_text(encoding="utf-8")
        # Simple Chunking (by empty lines / paragraphs)
        chunks = [p.strip() for p in text.split("\n\n") if p.strip()]
        
        logger.info(f"Processing {file_path.name} | chunks={len(chunks)} | slug={slug}")

        for content in chunks:
            chunk_id = str(uuid.uuid4())
            chunk = Chunk(
                id=chunk_id,
                text=content,
                character=character,
                character_slug=slug,
                chunk_type="quote",
                metadata={"source": file_path.name}
            )
            
            # Embed
            v = embedder.embed([chunk.to_embedding_text()])[0]
            vectors.append(v)
            metadatas.append(chunk.to_vector_metadata())

    # 2. Process Global Knowledge
    process_file(DATA_FILE, "Konex Guide", "konex-guide")

    # 3. Process Persona Knowledge (Hybrid RAG)
    knowledge_dir = Path("data/knowledge")
    if knowledge_dir.exists():
        for f in knowledge_dir.glob("*.md"):
            # slug = filename (e.g. 'support_haiti.md' -> 'support_haiti')
            process_file(f, f.stem, f.stem)

    # 4. Persist
    if vectors:
        vectorstore.add(vectors, metadatas, persist=True)
        logger.success(f"Ingested {len(vectors)} chunks into {VECTORSTORE_PATH}")
    else:
        logger.warning("No chunks to ingest.")

if __name__ == "__main__":
    ingest_konex()
