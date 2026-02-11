from typing import List, Dict, Tuple

from app.logger import setup_logger
from app.llm import get_embedder
from app.rag.vectorstore import VectorStore

logger = setup_logger().bind(name="rag.retriever")

DEFAULT_K = 5
RECALL_K = 20

CHUNK_TYPE_WEIGHTS = {
    "persona_seed": 3.0,
    "quote": 2.0,
    "action": 2.0,
    "summary_line": 1.0,
}

SPEAKER_MATCH_BONUS = 2.0
MENTION_MATCH_BONUS = 1.5
SUMMARY_LINE_BONUS = 0.5
NON_PERSONA_PENALTY = -0.5


class Retriever:
    """
    Read-only retrieval interface over the vector store.
    Responsible for recall, filtering, and reranking.
    """

    def __init__(self, vectorstore: VectorStore):
        self.vectorstore = vectorstore
        self.embedder = get_embedder()

        logger.success("Retriever Initialized")

    def _score_chunk(
        self, distance: float, metadata: Dict, active_character: str
    ) -> Dict:
        """
        Essentially, what's happening here is that i have implemented a score based reranking/filtering mechanism, so there are 3 types of positive retention capabilities which decide if a chunk needs to be dropped or not, once filtering is done, it gets sorted out on the basis of this exact score too, but that is not done here.

        the 3 points are:
        1. if the speaker of the chunk is equal to the character being talked to. +2.0
        2. if the character(s) mentioned in the chunk contain the character being talked to. +1.5
        3. if the chunk is of type 'summary_line'. +0.5

        If none of these criteria are met, the chunk receives a penalty of -0.5 and gets dropped.
        """
        """
        Compute a soft persona-aware score for a chunk.
        """
        chunk_type = metadata.get("chunk_type", "summary_line")
        speaker = metadata.get("character_slug")
        mentions = metadata.get("character_mentions", [])

        score = 1.0 / (1.0 + distance)

        score += CHUNK_TYPE_WEIGHTS.get(chunk_type, 1.0)

        if speaker == active_character:
            score += SPEAKER_MATCH_BONUS

        if active_character in mentions:
            score += MENTION_MATCH_BONUS

        if chunk_type == "summary_line":
            score += SUMMARY_LINE_BONUS

        if (
            speaker is not None
            and speaker != active_character
            and active_character not in mentions
            and chunk_type != "summary_line"
        ):
            score += NON_PERSONA_PENALTY

        return {
            "score": score,
            "text": metadata.get("text", ""),
            "metadata": metadata,
        }

    def _check_if_vectorstore_is_empty(vectorstore: VectorStore) -> bool:
        """
        Checks to see if the vectordb actually has any values or is empty.
        """
        return True if vectorstore.index.ntotal > 0 else False

    def retrieve(
        self, query: str, active_character: str, k: int = DEFAULT_K
    ) -> List[str]:
        """
        Retrieve relevant long-term memory for a given query and persona.
        """
        logger.info(f"Retrieving context | character={active_character} | k={k}")

        query_vector = self.embedder.embed([query])[0]

        # Hybrid RAG: Fetch more candidates to allow for strict filtering
        recalled = self.vectorstore.search(
            query_vector=query_vector,
            k=RECALL_K * 2, # Fetch double to ensure we have enough after filtering
        )

        filtered = []
        for distance, meta in recalled:
             chunk_slug = meta.get("character_slug")
             # Strict Filter: distinct slug MUST match.
             # If chunk has no slug (None), it's considered "Global/Common" knowledge.
             if chunk_slug and chunk_slug != active_character:
                 continue
             filtered.append((distance, meta))

        scored = [
            self._score_chunk(distance, meta, active_character)
            for distance, meta in filtered
        ]

        reranked = sorted(
            scored,
            key=lambda x: x["score"],
            reverse=True,
        )

        contexts = [item["text"] for item in reranked[:k]]

        logger.success(f"Retrieved context | returned={len(contexts)}")

        return contexts
