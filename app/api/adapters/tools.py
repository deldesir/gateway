from typing import Any, Dict, Optional
import asyncio

from fastapi import APIRouter, Header, HTTPException, Request, Depends
from loguru import logger
import os

from app.hermes.tools import get_hermes_tools  # Ensures tools are registered

router = APIRouter(tags=["tools"])

# CRM tools that benefit from typing indicators (ADR-011 T2)
_CRM_TOOLS = {"crm_list_groups", "crm_lookup_contact", "crm_org_info", "crm_create_group"}

INTERNAL_API_KEY = os.getenv("GATEWAY_INTERNAL_KEY", "")

async def verify_internal_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Validate that the caller is an authorized internal service (RiveBot).

    When GATEWAY_INTERNAL_KEY is not set, auth is skipped (dev mode) —
    matching the pattern in openai.py's _verify_api_key.
    """
    if not INTERNAL_API_KEY:
        return  # Dev mode — no auth required
    if x_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid internal API key")


async def _invoke_tool(tool_name: str, kwargs: Dict[str, Any], user_id: str,
                       context: Optional[Dict[str, str]] = None) -> str:
    """Resolve and invoke a registered tool. Returns the string result.

    Positional args support: if kwargs contains '_args' (a list of strings),
    they are mapped positionally to the tool's Pydantic schema field names.
    This lets macro_bridge pass space-split RiveScript args without knowing
    each tool's parameter names at the .rive authoring time.
    """
    tools = get_hermes_tools()
    tool_entry = tools.get(tool_name)
    
    if not tool_entry:
        raise HTTPException(status_code=404, detail=f"Unknown tool: '{tool_name}'")

    if "_args" in kwargs:
        pos_args: list = kwargs.pop("_args")
        schema = getattr(tool_entry, "schema", {})
        props = schema.get("parameters", {}).get("properties", {})
        
        # Exclude auto-injected active_* fields from positional mapping
        field_names = [k for k in props.keys() if not k.startswith("active_")]

        for i, val in enumerate(pos_args):
            if i < len(field_names) - 1:
                kwargs.setdefault(field_names[i], val)
            elif i == len(field_names) - 1:
                kwargs.setdefault(field_names[i], " ".join(pos_args[i:]))
                break

    kwargs.setdefault("user_id", user_id)

    if context:
        for key, val in context.items():
            kwargs.setdefault(key, val)

    # ADR-011 T2: Show "typing..." for CRM L2 commands (fire-and-forget)
    if tool_name in _CRM_TOOLS and user_id:
        try:
            from app.api.middleware.wuzapi_client import send_presence
            phone = user_id.split(":")[-1].lstrip("+") if ":" in user_id else user_id
            asyncio.create_task(send_presence(phone, "composing"))
        except Exception:
            pass  # best-effort — don't block the tool call

    try:
        # Hermes handlers are synchronous, we wrap them so they don't block RiveBot requests
        handler = getattr(tool_entry, "handler")
        result = await asyncio.to_thread(handler, kwargs if kwargs else {"user_id": user_id})
    except Exception as e:
        logger.error(f"[tools] {tool_name} raised {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Tool '{tool_name}' failed: {e}")

    return str(result)



@router.post("/v1/tools/{tool_name}", dependencies=[Depends(verify_internal_key)])
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


@router.get("/v1/tools/{tool_name}", dependencies=[Depends(verify_internal_key)])
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
