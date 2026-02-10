from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

ChunkType = Literal[
    "quote", "action", "summary_line", "persona_seed", "dialogue_composite"
]


@dataclass
class Chunk:
    """
    So essentially, we are defining the 'schema' for the json chunks to have these fields mandatorily along with the type of each variable explicitly defined so that no other data type can be inside any variable (key) nor can any other key be accepted.
    """

    """
    Canonical representation of a single RAG memory unit.

    Every JSONL line MUST normalize into exactly one Chunk.
    """

    id: str

    text: str

    character: str = "Konex"
    character_slug: str = "konex"

    # Generic Source Context
    source_uri: Optional[str] = None  # URL, filename, or unique source identifier
    timestamp: Optional[str] = None   # For audio/video transcripts
    segment_id: Optional[str] = None  # Granular reference (e.g. page number, slide ID)
    context_summary: Optional[str] = None # previously episode_title

    chunk_type: ChunkType = "quote"

    metadata: Dict = field(default_factory=dict)

    def to_embedding_text(self) -> str:
        """
        This method is created to send out only the 'text' field from the entire chunk and can be called by the object of the 'Chunk' class. This makes it simpler for the text to be extracted from each chunk and then passing it to the vector embedding model, as currently we only decided to embed the raw text as everything else is just either a single word or an id.

        in case if we wanna vectorize something else in the future, we can return that here as well.
        """
        """
        Text actually sent to the embedding model.

        This intentionally excludes metadata and IDs to keep
        embeddings semantically pure.
        """
        return self.text.strip()

    def to_vector_metadata(self) -> Dict:
        """
        This method is used to generate the metadata which will be stored for easy filtering, it essentially just removes the 'text' from the chunk and adds all the other fields in the metadata key.
        """
        """
        Metadata stored alongside the vector in the vector DB.
        Used for filtering and retrieval logic.
        """
        return {
            "id": self.id,
            "character": self.character,
            "text": self.text,
            "character_slug": self.character_slug,
            "chunk_type": self.chunk_type,
            "character_slug": self.character_slug,
            "chunk_type": self.chunk_type,
            "source_uri": self.source_uri,
            "timestamp": self.timestamp,
            "segment_id": self.segment_id,
            "context_summary": self.context_summary,
            **self.metadata,
        }
