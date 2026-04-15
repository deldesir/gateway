"""
Tool adapter layer — bridges LangChain @tool functions to Hermes Agent.

V1 tools use LangChain's @tool decorator with async signatures:
    @tool
    async def fetch_dossier(urn: str) -> str: ...

Hermes tools use a different pattern:
    def handler(args: dict, **kw) -> str: ...
    registry.register("fetch_dossier", handler, description="...")

This module provides adapters that wrap existing V1 tools for Hermes,
plus new MemPalace tools that use the _current_urn ContextVar for
tenant isolation.
"""

import asyncio
import logging
import os
from typing import Callable

from app.hermes.engine import _current_urn

logger = logging.getLogger(__name__)


# ── Adapter: LangChain @tool → Hermes handler ───────────────────────────────

def _wrap_langchain_tool(lc_tool) -> Callable:
    """
    Wrap a LangChain @tool function for Hermes's tool registry.

    LangChain tools have .ainvoke(args) → result.
    Hermes tools are sync: handler(args, **kw) → str.
    We bridge by running the async tool in a new event loop
    (safe because we're already in a thread pool worker).
    """
    def handler(args: dict, **kw) -> str:
        try:
            # We're in a thread pool worker — no running event loop
            result = asyncio.run(lc_tool.ainvoke(args))
            return str(result)
        except RuntimeError:
            # Fallback: if there IS a running loop (shouldn't happen),
            # use loop.run_until_complete
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(lc_tool.ainvoke(args))
            return str(result)

    handler.__name__ = getattr(lc_tool, "name", lc_tool.__name__)
    handler.__doc__ = getattr(lc_tool, "description", lc_tool.__doc__ or "")
    return handler


# ── MemPalace tools (new in V2) ─────────────────────────────────────────────

def search_memory(args: dict, **kw) -> str:
    """Search the user's memory palace for relevant past conversations.

    Args:
        query (str): Natural language search query
        wing (str, optional): Scope search to a specific wing
    """
    from mempalace.mcp_server import tool_search

    query = args.get("query", "")
    wing = args.get("wing")

    # Server-side wing injection: use the URN-derived wing, not user input
    urn = _current_urn.get()
    if urn:
        # Each WhatsApp user gets their own wing for tenant isolation
        wing = f"wa_{urn.split(':')[-1].lstrip('+')}"

    result = tool_search(query=query, wing=wing, n_results=5)
    return str(result)


def store_memory(args: dict, **kw) -> str:
    """Store a fact or note in the user's memory palace.

    Args:
        content (str): The content to store
        room (str, optional): Topic/room to file under
    """
    from mempalace.mcp_server import tool_store

    urn = _current_urn.get()
    wing = f"wa_{urn.split(':')[-1].lstrip('+')}" if urn else "default"

    content = args.get("content", "")
    room = args.get("room", "general")

    result = tool_store(content=content, wing=wing, room=room)
    return str(result)


def recall_memory(args: dict, **kw) -> str:
    """Get the status and overview of the memory palace.

    No arguments required — returns palace statistics.
    """
    from mempalace.mcp_server import tool_status
    result = tool_status()
    return str(result)


# ── Tool registration ───────────────────────────────────────────────────────

_registered = False


def register_all_tools() -> None:
    """
    Register all V1 tools + new V2 tools with the Hermes Agent.

    Called once during app lifespan startup. This function:
    1. Wraps each existing LangChain @tool with the adapter
    2. Registers new MemPalace tools
    3. Logs the final tool count for operational visibility

    Tools are only registered if Hermes is available. On import failure,
    a warning is logged and the gateway falls back to V1 LangGraph.
    """
    global _registered
    if _registered:
        return

    try:
        from run_agent import AIAgent
    except ImportError:
        logger.warning("Hermes Agent not available — skipping tool registration")
        return

    # V1 tools to migrate (import lazily to avoid circular imports)
    from app.graph.tools.registry import ToolRegistry as V1Registry

    v1_tools = V1Registry.all_tools()
    registered_count = 0

    for tool in v1_tools:
        tool_name = getattr(tool, "name", getattr(tool, "__name__", str(tool)))
        wrapped = _wrap_langchain_tool(tool)
        # Store in a module-level registry for Hermes to discover
        _hermes_tools[tool_name] = {
            "handler": wrapped,
            "description": getattr(tool, "description", wrapped.__doc__ or ""),
        }
        registered_count += 1

    # V2 MemPalace tools
    _hermes_tools["search_memory"] = {
        "handler": search_memory,
        "description": search_memory.__doc__,
    }
    _hermes_tools["store_memory"] = {
        "handler": store_memory,
        "description": store_memory.__doc__,
    }
    _hermes_tools["recall_memory"] = {
        "handler": recall_memory,
        "description": recall_memory.__doc__,
    }

    _registered = True
    logger.info(
        f"V2 tool registration complete: {registered_count} V1 tools + "
        f"3 MemPalace tools = {registered_count + 3} total"
    )


# Module-level tool store (populated by register_all_tools)
_hermes_tools: dict = {}


def get_hermes_tools() -> dict:
    """Return the registered tool dict for Hermes to consume."""
    if not _registered:
        register_all_tools()
    return _hermes_tools
