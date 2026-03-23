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


async def _run_migrations(conn):
    """Add new columns to existing tables if they don't exist.

    SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN,
    so we catch the 'duplicate column' error and move on.
    """
    from sqlalchemy import text

    migrations = [
        # Persona: add slug column
        "ALTER TABLE konex_personas ADD COLUMN slug VARCHAR",
        # Persona: add language column with default
        "ALTER TABLE konex_personas ADD COLUMN language VARCHAR DEFAULT 'ht'",
    ]

    for sql in migrations:
        try:
            await conn.execute(text(sql))
        except Exception:
            pass  # Column already exists

    # Backfill: set slug = name for any rows where slug is NULL
    try:
        await conn.execute(
            text("UPDATE konex_personas SET slug = name WHERE slug IS NULL")
        )
    except Exception:
        pass


async def init_db():
    async with engine.begin() as conn:
        # Create any new tables
        await conn.run_sync(SQLModel.metadata.create_all)
        # Migrate existing tables (add new columns)
        await _run_migrations(conn)
