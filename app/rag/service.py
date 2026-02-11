from typing import List, Optional
import time
import uuid

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeItem, KnowledgeItemCreate
from app.rag import get_embedder, get_vectorstore
from app.rag.schema import Chunk
from app.logger import setup_logger

logger = setup_logger().bind(name="rag.service")

class KnowledgeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.vectorstore = get_vectorstore()
        self.embedder = get_embedder()

    async def add_item(self, item_in: KnowledgeItemCreate) -> KnowledgeItem:
        """
        Add item to DB and Index.
        """
        # 1. DB Persist
        db_item = KnowledgeItem.model_validate(item_in)
        db_item.created_at = int(time.time())
        db_item.updated_at = int(time.time())
        
        self.session.add(db_item)
        await self.session.commit()
        await self.session.refresh(db_item)
        
        # 2. Indexing (Sync for now, could be background task)
        self._index_item(db_item)
        
        return db_item

    async def delete_item(self, item_id: str):
        """
        Delete from DB and Trigger Re-index (Naive approach).
        """
        statement = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        results = await self.session.execute(statement)
        item = results.scalar_one_or_none()
        
        if item:
            await self.session.delete(item)
            await self.session.commit()
            
            # Full Re-index required because FAISS doesn't support easy deletion by ID without ID map
            # For MVP: Re-index all.
            await self.reindex_all()

    async def reindex_all(self):
        """
        Clear index and re-ingest all items from DB.
        """
        logger.warning("Starting full re-index")
        
        # 1. Clear
        self.vectorstore.clear()
        
        # 2. Fetch All
        statement = select(KnowledgeItem)
        results = await self.session.execute(statement)
        items = results.scalars().all()
        
        # 3. Batch Index
        # Note: Ideally do this in batches.
        for item in items:
            self._index_item(item, persist=False)
            
        # 4. Final Persist
        self.vectorstore._persist()
        logger.success(f"Re-index complete | items={len(items)}")

    def _index_item(self, item: KnowledgeItem, persist: bool = True):
        """
        Helper to embed and add a single item.
        """
        # simple chunking (1 item = 1 chunk for now)
        chunk = Chunk(
            id=str(uuid.uuid4()),
            text=item.content,
            character="Konex Guide",
            source_uri=item.source_uri or f"knowledge-item:{item.id}",
            metadata={"db_id": item.id, "title": item.title}
        )
        
        vector = self.embedder.embed([chunk.to_embedding_text()])[0]
        
        self.vectorstore.add([vector], [chunk.to_vector_metadata()], persist=persist)
