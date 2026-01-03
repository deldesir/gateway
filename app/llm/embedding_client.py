from abc import ABC, abstractmethod
from typing import List


class EmbeddingClient(ABC):
    """
    Abstract interface for embedding models.
    """

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings for a list of texts.

        Args:
            texts (List[str]): Input texts.

        Returns:
            List[List[float]]: One embedding per text.
        """
        pass


