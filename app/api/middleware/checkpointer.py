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
POSTGRES_URI = os.getenv("POSTGRES_URI")


@asynccontextmanager
async def get_checkpointer():
    """Yield an initialised async checkpointer (Postgres or SQLite)."""
    if POSTGRES_URI and AsyncPostgresSaver:
        async with AsyncPostgresSaver.from_conn_string(POSTGRES_URI) as cp:
            yield cp
    else:
        async with AsyncSqliteSaver.from_conn_string(DB_PATH) as cp:
            yield cp
