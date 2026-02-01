from fastapi import FastAPI
from app.api.routes import router


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(title="scranton-agent", version="1.0.0")
    app.include_router(router)
    return app


app = create_app()
