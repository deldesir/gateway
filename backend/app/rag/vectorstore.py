from pathlib import Path
from typing import List, Dict, Tuple

import faiss
import pickle
import numpy as np

from app.logger import setup_logger

logger = setup_logger().bind(name="rag.vectorstore")


class VectorStore:
    """
    Essentially, here we define the path for storing the index, and the metadata file and also write functions to actually add stuff to the index and even search the index, so basically all the things needed with Faiss in the main langgraph code will be present here in this one class itself. Neat, right? I know. (i know everyone does this by default but i just wanna appreciate the beauty of clean code for once.)
    """

    """
    FAISS-backed vector store with disk persistence.
    """

    def __init__(self, index_path: Path, dim: int):
        """
        Args:
            index_path (Path): Directory where index + metadata are stored
            dim (int): Embedding dimensionality
        """
        self.index_path = index_path
        self.dim = dim

        self.index_file = index_path / "index.faiss"
        self.meta_file = index_path / "metadata.pkl"

        self.index = None
        self.metadata: List[Dict] = []

        self._load_or_create()

    def _load_or_create(self):
        """
        This loads or creates the Faiss index, but only stores it inside it's memory, this is the one we use to actually query and all that shit, but for writing the files to the root folder, we call the '_persist' function defined below it.
        """
        """
        Load existing FAISS index and metadata if present,
        otherwise create a new index.
        """
        self.index_path.mkdir(parents=True, exist_ok=True)

        if self.index_file.exists() and self.meta_file.exists():
            logger.info("Loading existing FAISS index from disk")

            self.index = faiss.read_index(str(self.index_file))
            with open(self.meta_file, "rb") as f:
                self.metadata = pickle.load(f)

            logger.success(f"Vector store loaded | vectors={self.index.ntotal}")

        else:
            logger.info("Creating new FAISS index")

            self.index = faiss.IndexFlatL2(self.dim)
            self.metadata = []

            logger.success(f"New vector store initialized | dim={self.dim}")

    def _persist(self):
        """
        Persist FAISS index and metadata to disk.
        """
        logger.info("Persisting vector store to disk")

        faiss.write_index(self.index, str(self.index_file))

        with open(self.meta_file, "wb") as f:
            pickle.dump(self.metadata, f)

        logger.success(f"Vector store persisted | vectors={self.index.ntotal}")

    def add(
        self,
        vectors: List[List[float]],
        metadatas: List[Dict],
        persist: bool = True,
    ):
        """
        Add vectors and corresponding metadata to the store.

        Args:
            vectors (List[List[float]]): Embedding vectors
            metadatas (List[Dict]): Metadata per vector
            persist (bool): Whether to persist immediately
        """
        if len(vectors) != len(metadatas):
            raise ValueError("Vectors and metadata length mismatch")

        if not vectors:
            logger.warning("No vectors to add")
            return

        logger.info(f"Adding vectors | count={len(vectors)}")

        np_vectors = np.array(vectors).astype("float32")

        self.index.add(np_vectors)
        self.metadata.extend(metadatas)

        logger.success(f"Vectors added | total_vectors={self.index.ntotal}")

        if persist:
            self._persist()

    def search(
        self,
        query_vector: List[float],
        k: int = 5,
    ) -> List[Tuple[float, Dict]]:
        """
        Perform similarity search.

        Args:
            query_vector (List[float]): Query embedding
            k (int): Number of results

        Returns:
            List of (distance, metadata) tuples
        """
        if self.index.ntotal == 0:
            logger.warning("Search requested on empty index")
            return []

        query = np.array([query_vector]).astype("float32")

        distances, indices = self.index.search(query, k)

        results = []

        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue

            results.append((float(dist), self.metadata[idx]))

        logger.info(f"Search completed | returned={len(results)}")

        return results
