"""
Health check endpoint — probes LiteLLM proxy and the checkpointer DB.

Returns HTTP 200 when all services are operational, 503 when degraded.
"""

import importlib.metadata
import os

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.middleware.checkpointer import get_checkpointer

router = APIRouter(tags=["observability"])

_LITELLM_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:4000")
_LITELLM_KEY = os.getenv("OPENAI_API_KEY", "")


async def _probe_litellm() -> str:
    """Check if the LiteLLM proxy is reachable and authenticated."""
    try:
        headers = {"Authorization": f"Bearer {_LITELLM_KEY}"} if _LITELLM_KEY else {}
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{_LITELLM_BASE}/health", headers=headers)
        return "ok" if r.status_code == 200 else f"degraded ({r.status_code})"
    except Exception:
        return "unreachable"


async def _probe_db() -> str:
    """Check if the checkpointer DB is accessible."""
    try:
        async with get_checkpointer() as cp:
            if hasattr(cp, "setup"):
                await cp.setup()
        return "ok"
    except Exception as e:
        return f"error: {e}"


@router.get("/health")
async def health() -> JSONResponse:
    """Structured health check — probes LiteLLM proxy and DB.

    Returns:
        200 when operational, 503 if any critical service is down.
    """
    try:
        version = importlib.metadata.version("ai-gateway")
    except Exception:
        version = "dev"

    litellm_status, db_status = await _probe_litellm(), await _probe_db()
    is_ok = litellm_status == "ok" and db_status == "ok"

    return JSONResponse(
        status_code=200 if is_ok else 503,
        content={
            "status": "ok" if is_ok else "degraded",
            "version": version,
            "services": {"litellm": litellm_status, "db": db_status},
        },
    )
