from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.models import KnowledgeItem, KnowledgeItemCreate, KnowledgeItemRead
from app.rag.service import KnowledgeService

router = APIRouter()

@router.post("/items", response_model=KnowledgeItemRead)
async def create_item(
    item: KnowledgeItemCreate,
    session: AsyncSession = Depends(get_session)
):
    service = KnowledgeService(session)
    return await service.add_item(item)

@router.delete("/items/{item_id}")
async def delete_item(
    item_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
):
    service = KnowledgeService(session)
    # Re-indexing is slow, so we could theoretically offload it. 
    # For now, we await it to ensure consistency for the demo.
    await service.delete_item(item_id)
    return {"status": "deleted", "id": item_id}

@router.post("/reindex")
async def reindex(
    session: AsyncSession = Depends(get_session)
):
    service = KnowledgeService(session)
    await service.reindex_all()
    return {"status": "reindexed"}
