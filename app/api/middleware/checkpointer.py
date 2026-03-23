"""
Checkpointer factory — yields an async LangGraph checkpointer backed by
either PostgreSQL (if POSTGRES_URI is set) or SQLite (default).

Usage::

    async with get_checkpointer() as cp:
        graph = build_graph(checkpointer=cp)
"""

import os
from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:
    AsyncPostgresSaver = None  # type: ignore[assignment]

DB_PATH = os.getenv("SQLITE_DB_PATH", "checkpoints.sqlite")
_RAW_PG_URI = os.getenv("POSTGRES_URI")
# Strip SQLAlchemy driver suffix (e.g. "+asyncpg") so LangGraph's psycopg
# connector gets a plain "postgresql://..." string it can parse.
POSTGRES_URI = _RAW_PG_URI.replace("+asyncpg", "") if _RAW_PG_URI else None


@asynccontextmanager
async def get_checkpointer():
    """Yield an initialised async checkpointer (Postgres or SQLite)."""
    if POSTGRES_URI and AsyncPostgresSaver:
        async with AsyncPostgresSaver.from_conn_string(POSTGRES_URI) as cp:
            yield cp
    else:
        async with AsyncSqliteSaver.from_conn_string(DB_PATH) as cp:
            yield cp
