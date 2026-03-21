"""
/v1/tools/* — Direct tool-dispatch endpoints for RiveBot macros.

RiveBot's macro_bridge calls these endpoints when a RiveScript brain uses
  <call>talkmaster_status</call>
  <call>import_talk s-34 topic-name My Theme</call>

Design:
- POST /v1/tools/{tool_name}  — body is a JSON dict of kwargs (may be empty)
- GET  /v1/tools/{tool_name}  — same, but no body (no-arg tools like talkmaster_status)
- The X-User-Id header scopes the call to a specific user (passed through to tools
  that accept a user_id; silently ignored for tools that don't).
- On success returns {"result": "<string>"}.
- On error returns 400 or 500 with {"detail": "<reason>"}.

Only tools in ToolRegistry are accessible. Attempting to call an unknown tool
returns 404.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from loguru import logger

from app.graph.tools.registry import ToolRegistry

router = APIRouter(tags=["tools"])


async def _invoke_tool(tool_name: str, kwargs: Dict[str, Any], user_id: str) -> str:
    """Resolve and invoke a registered tool. Returns the string result.

    Positional args support: if kwargs contains '_args' (a list of strings),
    they are mapped positionally to the tool's Pydantic schema field names.
    This lets macro_bridge pass space-split RiveScript args without knowing
    each tool's parameter names at the .rive authoring time.

    Example:
        _args=["s-34", "Courage", "Faith in times of trial"]
        → {pub_code="s-34", topic_name="Courage", theme="Faith..."}
    """
    try:
        tool_fn = ToolRegistry.get(tool_name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown tool: '{tool_name}'")

    # Map positional args to field names using the tool's schema
    if "_args" in kwargs:
        pos_args: list = kwargs.pop("_args")
        schema = getattr(tool_fn, "args_schema", None)
        if schema and hasattr(schema, "model_fields"):
            field_names = list(schema.model_fields.keys())
        elif schema and hasattr(schema, "__fields__"):
            field_names = list(schema.__fields__.keys())
        else:
            field_names = []
        for i, val in enumerate(pos_args):
            if i < len(field_names):
                kwargs.setdefault(field_names[i], val)
            # Extra positional args are dropped silently

    try:
        result = await tool_fn.ainvoke(kwargs if kwargs else {})
    except Exception as e:
        logger.error(f"[tools] {tool_name} raised {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Tool '{tool_name}' failed: {e}")

    return str(result)


@router.post("/v1/tools/{tool_name}")
async def call_tool_post(
    tool_name: str,
    request: Request,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> dict:
    """
    Invoke a tool by name, passing JSON body kwargs.
    Called by RiveBot macro_bridge for tools that need arguments.

    Example:
        POST /v1/tools/import_talk
        {"pub_code": "s-34", "topic_name": "Courage", "theme": "Faith"}
    """
    user_id = x_user_id or "rivebot"
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}

    logger.info(f"[tools] POST {tool_name} | user={user_id} | kwargs={list(body.keys())}")
    result = await _invoke_tool(tool_name, body, user_id)
    return {"result": result}


@router.get("/v1/tools/{tool_name}")
async def call_tool_get(
    tool_name: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> dict:
    """
    Invoke a no-argument tool by name.
    Called by RiveBot macro_bridge for simple status/list tools.

    Example:
        GET /v1/tools/talkmaster_status
        GET /v1/tools/list_publications
    """
    user_id = x_user_id or "rivebot"
    logger.info(f"[tools] GET {tool_name} | user={user_id}")
    result = await _invoke_tool(tool_name, {}, user_id)
    return {"result": result}
