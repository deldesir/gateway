from pathlib import Path

from app.llm import get_embedder
from app.rag.vectorstore import VectorStore


VECTORSTORE_PATH = Path("data/vectorstore")
EMBEDDING_DIM = 384  # MiniLM


def main():
    print("\nLoading vector store...")
    store = VectorStore(
        index_path=VECTORSTORE_PATH,
        dim=EMBEDDING_DIM,
    )

    print(f"Vector store loaded | total_vectors={store.index.ntotal}")

    embedder = get_embedder()

    query = "How do I register for an account?"

    print(f"\nQuery: {query}")

    query_vector = embedder.embed([query])[0]

    results = store.search(query_vector, k=5)

    print(results[0])
    print("\n")
    print(results[1])

    print("\nTop results:\n")

    for i, (distance, metadata) in enumerate(results, start=1):
        print(f"--- Result {i} ---")
        print(f"Distance     : {distance:.4f}")
        print(f"Character    : {metadata.get('character')}")
        print(f"Text    : {metadata.get('text')}")
        print(f"Chunk Type   : {metadata.get('chunk_type')}")
        print(f"Episode Code : {metadata.get('episode_code')}")
        print(f"Episode Title: {metadata.get('episode_title')}")
        print(f"Source URL   : {metadata.get('source_url')}")

        print()


if __name__ == "__main__":
    main()
