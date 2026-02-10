from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import router as chat_router
from app.api.personas import router as personas_router
from app.api.knowledge import router as knowledge_router
from app.db import init_db
import app.models  # Register SQLModel tables
import app.commands  # Register commands


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB
    await init_db()
    yield
    # Shutdown: Cleanup if needed


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(
        title="Konex Pro Backend",
        version="0.1.0",
        description="Agental logic for Konex services (IIAB)",
        lifespan=lifespan
    )
    app.include_router(chat_router)
    app.include_router(personas_router, prefix="/v1", tags=["personas"])
    app.include_router(knowledge_router, prefix="/v1/knowledge", tags=["knowledge"])
    return app


app = create_app()
