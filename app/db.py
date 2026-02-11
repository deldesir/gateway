from typing import AsyncGenerator
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
import os

# Database URL
# Default to SQLite for local dev, but production uses Postgres
DATABASE_URL = os.getenv("POSTGRES_URI", "sqlite+aiosqlite:///./checkpoints.sqlite")

# Engine
engine = create_async_engine(DATABASE_URL, echo=True, future=True)

# Session
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
