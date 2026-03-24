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


async def _invoke_tool(tool_name: str, kwargs: Dict[str, Any], user_id: str,
                       context: Optional[Dict[str, str]] = None) -> str:
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

    # Map positional args to field names using the tool's schema.
    # The LAST field acts as a catch-all: any remaining tokens are joined
    # with spaces so that multi-word values (like talk themes or section
    # titles) are not silently truncated.
    #
    # Example: _args=["s-34", "Courage", "Faith", "in", "times"]
    #   field_names = [pub_code, topic_name, theme]
    #   → {pub_code="s-34", topic_name="Courage", theme="Faith in times"}
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
            if i < len(field_names) - 1:
                # All but the last field: one positional arg each
                kwargs.setdefault(field_names[i], val)
            elif i == len(field_names) - 1:
                # Last field: join this and all remaining tokens
                kwargs.setdefault(field_names[i], " ".join(pos_args[i:]))
                break
            # If no schema fields, extra args are dropped

    # Inject user_id into kwargs so tools that accept it can use it.
    # Tools that don't declare user_id in their schema simply ignore it.
    kwargs.setdefault("user_id", user_id)

    # Inject active context from macro_bridge headers
    if context:
        for key, val in context.items():
            kwargs.setdefault(key, val)

    try:
        result = await tool_fn.ainvoke(kwargs if kwargs else {"user_id": user_id})
    except Exception as e:
        logger.error(f"[tools] {tool_name} raised {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Tool '{tool_name}' failed: {e}")

    return str(result)


@router.post("/v1/tools/{tool_name}")
async def call_tool_post(
    tool_name: str,
    request: Request,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_active_pub: Optional[str] = Header(None, alias="X-Active-Pub"),
    x_active_talk_id: Optional[str] = Header(None, alias="X-Active-Talk-Id"),
    x_active_revision: Optional[str] = Header(None, alias="X-Active-Revision"),
) -> dict:
    """
    Invoke a tool by name, passing JSON body kwargs.
    Called by RiveBot macro_bridge for tools that need arguments.
    """
    user_id = x_user_id or "rivebot"
    context = {}
    if x_active_pub: context["active_pub"] = x_active_pub
    if x_active_talk_id: context["active_talk_id"] = x_active_talk_id
    if x_active_revision: context["active_revision"] = x_active_revision

    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}

    logger.info(f"[tools] POST {tool_name} | user={user_id} | kwargs={list(body.keys())} | ctx={context}")
    result = await _invoke_tool(tool_name, body, user_id, context)
    return {"result": result}


@router.get("/v1/tools/{tool_name}")
async def call_tool_get(
    tool_name: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_active_pub: Optional[str] = Header(None, alias="X-Active-Pub"),
    x_active_talk_id: Optional[str] = Header(None, alias="X-Active-Talk-Id"),
    x_active_revision: Optional[str] = Header(None, alias="X-Active-Revision"),
) -> dict:
    """
    Invoke a no-argument tool by name.
    Called by RiveBot macro_bridge for simple status/list tools.
    """
    user_id = x_user_id or "rivebot"
    context = {}
    if x_active_pub: context["active_pub"] = x_active_pub
    if x_active_talk_id: context["active_talk_id"] = x_active_talk_id
    if x_active_revision: context["active_revision"] = x_active_revision

    logger.info(f"[tools] GET {tool_name} | user={user_id} | ctx={context}")
    result = await _invoke_tool(tool_name, {}, user_id, context)
    return {"result": result}
