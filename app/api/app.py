from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import router as chat_router
from app.api.personas import router as personas_router
from app.api.downloads import router as downloads_router
from app.db import init_db
from app.seed import seed_personas
import app.models  # Register SQLModel tables
import app.commands  # Register commands


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.hooks.siyuan_tools import _init_notebook_map
    from app.hermes.tools import register_all_tools
    
    # Startup: Initialize DB, then seed default personas
    await init_db()
    await seed_personas()
    
    # V2 Init: Pre-load SiYuan configuration and register Hermes tools
    _init_notebook_map()
    register_all_tools()
    
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
    app.include_router(downloads_router)
    return app


app = create_app()
