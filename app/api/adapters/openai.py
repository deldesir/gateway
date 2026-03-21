"""
OpenAI-compatible adapter for RapidPro → AI Gateway communication.

RapidPro calls ``POST /v1/chat/completions`` with an OpenAI-style payload.
This adapter:
  1. Parses the RapidPro message prefix to extract URN + channel
  2. Resolves the channel to a persona
  3. Dispatches admin commands (/ or # prefixed)
  4. Invokes the LangGraph and returns an OpenAI-shaped response
"""

import time
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.api.middleware.checkpointer import get_checkpointer
from app.api.middleware.message_parser import parse_rapidpro_message
from app.graph.graph import build_graph
from app.logger import logger
from app.services.auth import check_admin_permissions
from app.services.channel import resolve_persona

router = APIRouter(tags=["chat"])
api_logger = logger.bind(name="API")


# ── Schemas ───────────────────────────────────────────────────────────────────

class OpenAIChatMessage(BaseModel):
    role: str
    content: str


class OpenAIChatRequest(BaseModel):
    model: str
    messages: List[Dict[str, str]]
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7
    user: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _openai_response(
    model: str,
    content: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    id_prefix: str = "chatcmpl",
) -> dict:
    """Build a well-formed OpenAI chat.completion response dict."""
    return {
        "id": f"{id_prefix}-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _extract_usage(result: dict) -> tuple[int, int]:
    """Pull real token counts from the last AIMessage response_metadata."""
    messages = result.get("messages", [])
    if not messages:
        return 0, 0
    meta = getattr(messages[-1], "response_metadata", {}) or {}
    usage = meta.get("token_usage") or meta.get("usage") or {}
    return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/v1/chat/completions")
async def openai_chat_completions(
    request: OpenAIChatRequest,
    raw_request: Request,
) -> dict:
    """OpenAI-compatible chat endpoint consumed by RapidPro's AI LLM config."""
    api_logger.info(f"Incoming request | model={request.model} | user={request.user}")
    api_logger.debug(f"Headers: {dict(raw_request.headers)}")

    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    raw_content = request.messages[-1]["content"]

    # ── 1. Parse RapidPro message prefix ─────────────────────────────────────
    parsed = parse_rapidpro_message(raw_content, user_hint=request.user)
    api_logger.info(
        f"Parsed | user={parsed.user_id} | channel={parsed.channel_id}"
        f" | content='{parsed.content[:60]}'"
    )

    if not parsed.user_id:
        raise HTTPException(
            status_code=400,
            detail="Field 'user' is required for session isolation (e.g. phone number).",
        )

    # Update request with cleaned values
    request.messages[-1]["content"] = parsed.content
    if parsed.channel_id:
        request.model = parsed.channel_id

    user_id = parsed.user_id
    last_user_message = parsed.content

    # ── 2. Resolve persona from channel config ────────────────────────────────
    model_persona, system_prompt_override = await resolve_persona(
        request.model or "konex-support"
    )

    # ── 3. Build persona-scoped thread ID ─────────────────────────────────────
    thread_id = f"whatsapp:{user_id}:{model_persona}"

    # ── 4. Admin command dispatch ─────────────────────────────────────────────
    if last_user_message.strip().startswith(("/", "#")):
        parts = last_user_message.strip().split()
        command_root = parts[0].lower().strip("/#") if parts else ""
        is_allowed = await check_admin_permissions(user_id, command_root)

        from app.commands.registry import CommandRegistry, CommandContext

        if CommandRegistry.has_command(command_root):
            if not is_allowed:
                api_logger.warning(f"Access denied: '{command_root}' from {user_id}")
                return _openai_response(model_persona, "🚫 Permission Denied.", id_prefix="chatcmpl-deny")

        if is_allowed:
            async with get_checkpointer() as cp:
                if hasattr(cp, "setup"):
                    await cp.setup()
                ctx = CommandContext(
                    user_id=user_id,
                    thread_id=thread_id,
                    persona=model_persona,
                    args=[],
                    checkpointer=cp,
                    raw_message=last_user_message,
                )
                admin_response = await CommandRegistry.execute(last_user_message, ctx)

            if admin_response:
                return _openai_response(
                    model_persona, admin_response, id_prefix="chatcmpl-admin"
                )

    # ── 4.5 Deterministic intent router (zero tokens) ────────────────────────
    from app.api.middleware.rivebot_client import match_intent
    try:
        intent_response = await match_intent(last_user_message, model_persona, user_id)
        if intent_response is not None:
            return _openai_response(
                model_persona, intent_response, id_prefix="chatcmpl-rs"
            )
    except Exception as e:
        logger.error(f"Rivebot match error: {e}")
        # On error, safely fall through to LangGraph

    # ── 5. LangGraph invocation ───────────────────────────────────────────────
    async with get_checkpointer() as cp:
        if hasattr(cp, "setup"):
            await cp.setup()
        graph = build_graph(checkpointer=cp)
        result = await graph.ainvoke(
            {
                "persona": model_persona,
                "user_input": last_user_message,
                "messages": [HumanMessage(content=last_user_message)],
                "system_prompt_override": system_prompt_override,
            },
            config={"configurable": {"thread_id": thread_id}},
        )

    final_text = result.get("final_response") or "Mwen pa konprann."
    prompt_tokens, completion_tokens = _extract_usage(result)

    # ── 5.5 Advance RiveBot topic if a stage-completing tool ran ──────────────
    from app.api.middleware.rivebot_client import (
        detect_stage_completing_tool,
        advance_topic_if_needed,
    )
    stage_tool = detect_stage_completing_tool(result)
    if stage_tool:
        await advance_topic_if_needed(stage_tool, model_persona, user_id)

    return _openai_response(
        model_persona, final_text, prompt_tokens, completion_tokens
    )
