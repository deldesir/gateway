"""
OpenAI-compatible adapter for RapidPro → AI Gateway communication.

RapidPro calls ``POST /v1/chat/completions`` with an OpenAI-style payload.
This adapter:
  1. Parses the RapidPro message prefix to extract URN + channel
  2. Resolves the channel to a persona
  3. Dispatches admin commands (/ or # prefixed)
  4. Invokes Hermes Agent and returns an OpenAI-shaped response
"""

import asyncio
import os
import time
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel

from app.api.middleware.message_parser import parse_rapidpro_message
from app.logger import logger
from app.services.auth import check_admin_permissions
from app.services.channel import resolve_persona, DEFAULT_PERSONA
from app.hermes.engine import invoke_hermes

router = APIRouter(tags=["chat"])
api_logger = logger.bind(name="API")

# ── API Key Authentication (F-30) ────────────────────────────────────────────
# When GATEWAY_API_KEY is set, all requests must include it.
# When unset, dev mode — no auth required.
def _parse_authorized_users() -> dict:
    """Parse AUTHORIZED_USERS env var into a phone→name lookup dict."""
    raw = os.getenv("AUTHORIZED_USERS", "")
    if not raw:
        return {}
    result = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" in entry:
            phone, name = entry.split(":", 1)
            phone = phone.strip().replace("+", "").replace("whatsapp:", "")
            result[phone] = name.strip()
    return result

_AUTHORIZED_USERS: dict = _parse_authorized_users()

if not _AUTHORIZED_USERS:
    import logging as _gw_log
    _gw_log.getLogger(__name__).warning(
        "AUTHORIZED_USERS is not set — access gate disabled (open dev mode). "
        "Set AUTHORIZED_USERS=phone:Name,... to restrict access."
    )

_API_KEY = os.getenv("GATEWAY_API_KEY", "")


async def _verify_api_key(raw_request: Request):
    """Verify API key if configured. Skip in dev mode (no key set)."""
    if not _API_KEY:
        return  # Dev mode — no auth
    key = (
        raw_request.headers.get("X-API-Key")
        or raw_request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    )
    if key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# In-memory cache: user_id → preferred persona slug
# Set when {{persona_switch}} fires, checked before channel default.
_user_persona: Dict[str, str] = {}

# ── Session file persistence for cross-tier continuity (F-14) ─────────────────
import json
from pathlib import Path

_sessions_dir = Path(os.getenv(
    "HERMES_HOME", str(Path.home() / ".hermes")
)) / "sessions"


def _persist_rivebot_turn(session_id: str, user_msg: str, bot_response: str):
    """Append a RiveBot-handled turn to the Hermes session file.

    This ensures Hermes sees RiveBot exchanges in conversation_history
    on the next turn, maintaining cross-tier continuity.
    """
    if not bot_response:
        return
    _sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = _sessions_dir / f"session_{session_id}.json"
    try:
        data = json.loads(session_file.read_text()) if session_file.exists() else {"messages": []}
        data["messages"].append({"role": "user", "content": user_msg})
        data["messages"].append({"role": "assistant", "content": f"[RiveBot] {bot_response}"})
        session_file.write_text(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        api_logger.warning(f"Failed to persist RiveBot turn: {e}")

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

@router.post("/v1/chat/completions", dependencies=[Depends(_verify_api_key)])
@router.post("/chat/completions", dependencies=[Depends(_verify_api_key)])
async def openai_chat_completions(
    request: OpenAIChatRequest,
    raw_request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """OpenAI-compatible chat endpoint consumed by RapidPro's AI LLM config."""
    api_logger.info(f"Incoming request | model={request.model} | user={request.user}")
    api_logger.debug(f"Headers: {dict(raw_request.headers)}")

    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    if len(request.messages) > 1:
        api_logger.warning(
            f"Received {len(request.messages)} messages in payload, using last only"
        )

    raw_content = request.messages[-1]["content"]

    # ── 1. Parse RapidPro message prefix ─────────────────────────────────────
    # RapidPro may include attachments in the last message or as a top-level field.
    raw_attachments = request.messages[-1].get("attachments", [])
    parsed = parse_rapidpro_message(raw_content, user_hint=request.user,
                                    attachments=raw_attachments)
    api_logger.info(
        f"Parsed | user={parsed.user_id} | channel={parsed.channel_id}"
        f" | content='{parsed.content[:60]}'"
    )

    if not parsed.user_id:
        api_logger.warning("Missing 'user' field in request — rejecting (F-10).")
        return _openai_response(
            DEFAULT_PERSONA, "{{noreply}}", id_prefix="chatcmpl-nouser"
        )

    # Update request with cleaned values
    request.messages[-1]["content"] = parsed.content
    if parsed.channel_id:
        request.model = parsed.channel_id

    user_id = parsed.user_id
    last_user_message = parsed.content

    # ── 1.6 Authorization gate (F-26) ────────────────────────────────────────
    # Check BEFORE RiveBot, commands, or Hermes — blocks all code paths.
    if _AUTHORIZED_USERS:
        user_digits = user_id.replace("+", "").split(":")[-1]
        if user_digits not in _AUTHORIZED_USERS:
            api_logger.warning(f"Unauthorized user {user_id} — silent drop")
            return _openai_response(
                DEFAULT_PERSONA, "", id_prefix="chatcmpl-unauth"
            )

    # ── 1.5  Attachment handling ─────────────────────────────────────────────
    if parsed.attachments:
        # Check if any attachment or the message text mentions .jwpub
        is_jwpub = ".jwpub" in last_user_message.lower()
        jwpub_url = None

        for att in parsed.attachments:
            att_str = att if isinstance(att, str) else str(att)
            # Check attachment URL/name for .jwpub
            if ".jwpub" in att_str.lower():
                is_jwpub = True
            # Extract URL from "content_type:http://..." format
            if is_jwpub and jwpub_url is None:
                # Find the URL portion (starts with http)
                http_idx = att_str.find("http")
                if http_idx >= 0:
                    jwpub_url = att_str[http_idx:]
                elif ":" in att_str:
                    # Fallback: split on first colon after mime type
                    parts = att_str.split(":", maxsplit=2)
                    jwpub_url = ":".join(parts[1:]) if len(parts) > 1 else att_str
                else:
                    jwpub_url = att_str

        if is_jwpub and jwpub_url:
            api_logger.info(f"JWPUB detected — routing to upload_jwpub (AI-free): {jwpub_url}")
            try:
                from app.graph.tools.upload import upload_jwpub
                result = await upload_jwpub.ainvoke({"media_url": jwpub_url})
            except Exception as e:
                result = f"❌ Error processing .jwpub file: {e}"

            # Auto-switch to talkprep persona after successful jwpub upload
            _user_persona[user_id] = "talkprep"
            target_thread_id = f"whatsapp:{user_id}:talkprep"
            
            # Persist this system action into the destination session file
            # so the TalkPrep AI is aware that the presentation was just processed
            _persist_rivebot_turn(
                target_thread_id,
                user_msg=f"[SysAction] User uploaded presentation: {jwpub_url}",
                bot_response=f"[SysAction] Upload result: {result}"
            )
            
            api_logger.info(f"Auto-switched {user_id} to talkprep persona after jwpub upload")

            return _openai_response(
                "talkprep", result,
                id_prefix="chatcmpl-jwpub",
            )

        # Non-jwpub attachments: inject context for AI
        att_lines = []
        for att in parsed.attachments:
            parts = att.split(":", 1) if isinstance(att, str) else []
            if len(parts) == 2:
                att_lines.append(f"[Attachment: {parts[0]} at {parts[1]}]")
            else:
                att_lines.append(f"[Attachment: {att}]")
        last_user_message = last_user_message + "\n" + "\n".join(att_lines)


    # ── 2. Resolve persona from user preference or channel config ─────────────
    # User preference (from previous persona switch) takes priority
    preferred = _user_persona.get(user_id)
    if preferred:
        model_persona, system_prompt_override = await resolve_persona(preferred)
        api_logger.info(f"Using preferred persona for {user_id}: {model_persona}")
    else:
        # First try resolving by user_id to hit the ChannelConfig table
        model_persona, system_prompt_override = await resolve_persona(user_id)
        
        # If it fell back to default, and request.model is provided and not generic, use it:
        if model_persona == DEFAULT_PERSONA and request.model and request.model != "custom_ai":
            model_persona, system_prompt_override = await resolve_persona(request.model)

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
            from app.commands.registry import CommandRegistry, CommandContext
            ctx = CommandContext(
                user_id=user_id,
                thread_id=thread_id,
                persona=model_persona,
                args=[],
                checkpointer=None,  # V1 checkpointer disabled in V2
                raw_message=last_user_message,
            )
            admin_response = await CommandRegistry.execute(last_user_message, ctx)

            if admin_response:
                return _openai_response(
                    model_persona, admin_response, id_prefix="chatcmpl-admin"
                )

    # ── 4.5 Deterministic intent router (zero tokens) ────────────────────────
    from app.api.middleware.rivebot_client import match_intent, set_var, set_vars
    rivebot_context = {}
    try:
        # Inject WhatsApp contact name if available (skips onboarding name question)
        if parsed.contact_name:
            try:
                await set_vars(model_persona, user_id, {
                    "name": parsed.contact_name,
                    "onboarded": "true",
                    "welcomed": "true",
                })
            except Exception:
                pass  # non-critical: onboarding will ask for name instead

        intent_response, rivebot_context = await match_intent(
            last_user_message, model_persona, user_id
        )
        rivebot_context["urn"] = user_id
        # NoAI silence: 3rd+ fallback → send nothing to the user
        if rivebot_context.get("silent"):
            # ── Smart silent: check if user is responding to an AI turn ──
            # If the last assistant message in the session was from Hermes
            # (not [RiveBot]), the user is likely answering an AI question.
            # In that case, ignore the silent flag and forward to AI.
            _last_was_ai = False
            try:
                session_file = _sessions_dir / f"session_{thread_id}.json"
                if session_file.exists():
                    _sdata = json.loads(session_file.read_text())
                    _smsgs = _sdata.get("messages", [])
                    # Find last assistant message
                    for _m in reversed(_smsgs):
                        if _m.get("role") == "assistant":
                            _last_was_ai = not _m.get("content", "").startswith("[RiveBot]")
                            break
            except Exception:
                pass

            if _last_was_ai:
                api_logger.info(f"Silent trigger for {user_id} — overriding (last turn was AI)")
                # Fall through to Hermes Agent (skip the silent handler)
            else:
                api_logger.info(f"Silent trigger for {user_id} — emoji reaction")

                # Best-effort: send context-aware reaction via WuzAPI
                if parsed.external_msg_id and parsed.user_id:
                    phone = parsed.user_id.split(":")[-1].lstrip("+")
                    _msg = last_user_message.strip().lower()
                    _reaction_map = {
                        "ok": "👍🏾", "okay": "👍🏾", "yes": "👍🏾", "yep": "👍🏾",
                        "no": "👌🏾", "nah": "👌🏾", "nope": "👌🏾",
                        "lol": "😁", "haha": "😁", "😂": "😁",
                        "cool": "😊", "nice": "😊", "great": "😊",
                        "thanks": "🙏🏾", "thank you": "🙏🏾", "thx": "🙏🏾",
                        "bye": "👋🏾", "later": "👋🏾", "ciao": "👋🏾",
                        "wow": "😉", "oh": "😉",
                    }
                    emoji = _reaction_map.get(_msg, "👍🏾")
                    try:
                        from app.api.middleware.wuzapi_client import send_reaction, mark_as_read
                        await send_reaction(phone, parsed.external_msg_id, emoji)
                        await mark_as_read(phone, parsed.external_msg_id)
                    except Exception as e:
                        api_logger.debug(f"WuzAPI reaction/read failed (non-critical): {e}")

                # Return {{noreply}} sentinel — RapidPro flow must check for this
                # and skip sending. This avoids blank WhatsApp messages.
                return _openai_response(model_persona, "{{noreply}}", id_prefix="chatcmpl-silent")

        # Persona switch: re-route to new persona
        if rivebot_context.get("switch_persona"):
            new_slug = rivebot_context["switch_persona"]

            # ── Permission check (Finding 15) ────────────────────────────────
            # If the target persona has allowed_urns set, verify the user is authorized
            try:
                from app.db import async_session
                from app.models import Persona
                from sqlmodel import select

                async with async_session() as session:
                    result = await session.execute(
                        select(Persona).where(Persona.slug == new_slug)
                    )
                    target_persona = result.scalar_one_or_none()
                    if target_persona and target_persona.allowed_urns:
                        if user_id not in target_persona.allowed_urns:
                            api_logger.warning(
                                f"Persona switch DENIED: {user_id} → {new_slug} "
                                f"(not in allowed_urns)"
                            )
                            return _openai_response(
                                model_persona,
                                "⚠️ Ou pa gen aksè nan sèvis sa a.",
                                id_prefix="chatcmpl-denied",
                            )
            except Exception as e:
                api_logger.warning(f"Persona permission check failed (allowing): {e}")

            _user_persona[user_id] = new_slug  # Persist preference
            model_persona = new_slug
            thread_id = f"whatsapp:{user_id}:{new_slug}"
            api_logger.info(f"Persona switch: {user_id} → {new_slug} (preference saved)")

            # NOTE: Global user state (lang, name, onboarded, welcomed) is auto-propagated
            # across all persona engines by RiveBot's set_uservar() — no manual carry-over needed.

            # Send a greeting via the new persona
            try:
                greet_resp, _ = await match_intent("bonjou", new_slug, user_id)
                if greet_resp:
                    return _openai_response(
                        new_slug, f"🔄 {greet_resp}", id_prefix="chatcmpl-switch"
                    )
            except Exception:
                pass
            return _openai_response(
                new_slug,
                "🔄 Pase nan " + new_slug.replace("-", " ").title() + ". Kijan m ka ede w?",
                id_prefix="chatcmpl-switch",
            )

        if intent_response is not None:
            # Best-effort: react to greetings/thanks even when sending a text reply
            if parsed.external_msg_id and parsed.user_id:
                _msg = last_user_message.strip().lower()
                _greeting_reactions = {
                    "hello": "👋🏾", "hi": "👋🏾", "hey": "👋🏾",
                    "bonjou": "👋🏾", "salut": "👋🏾", "alo": "👋🏾",
                    "thanks": "🙏🏾", "thank you": "🙏🏾", "mesi": "🙏🏾", "merci": "🙏🏾",
                    "bye": "👋🏾", "orevwa": "👋🏾", "kenbe": "👋🏾",
                }
                react_emoji = _greeting_reactions.get(_msg)
                if react_emoji:
                    phone = parsed.user_id.split(":")[-1].lstrip("+")
                    try:
                        from app.api.middleware.wuzapi_client import send_reaction
                        await send_reaction(phone, parsed.external_msg_id, react_emoji)
                    except Exception:
                        pass
            # ── Persist RiveBot turn to session file (F-14) ─────────────
            _persist_rivebot_turn(thread_id, last_user_message, intent_response)

            return _openai_response(
                model_persona, intent_response, id_prefix="chatcmpl-rs"
            )
    except Exception as e:
        logger.error(f"Rivebot match error: {e}")
        # On error, safely fall through to Hermes Agent

    # ── 5. Hermes Agent invocation ───────────────────────────────────────────────
    try:
        # Resolve persona properties
        from app.graph.prompts import PersonaPromptRegistry
        persona_vars = await PersonaPromptRegistry.get_async(model_persona)

        # Check allowed_urns for resolved persona (not just switches)
        if persona_vars.get("allowed_urns"):
            if user_id not in persona_vars["allowed_urns"]:
                api_logger.warning(f"Persona access DENIED: {user_id} → {model_persona}")
                return _openai_response(
                    model_persona,
                    "⚠️ Ou pa gen aksè nan sèvis sa a.",
                    id_prefix="chatcmpl-denied",
                )

        # ── 4.9 Allowed URNs gate (persona-level access control) ──────────────
        # Note: global access gate is already applied above at step 1.6.

        # ── Tier 3 Reaction Plumbing (Finding 22) ──────────────
        _phone = None
        _msg_id = None
        if parsed.external_msg_id and parsed.user_id:
            _phone = parsed.user_id.split(":")[-1].lstrip("+")
            _msg_id = parsed.external_msg_id
            try:
                from app.api.middleware.wuzapi_client import send_reaction
                asyncio.create_task(send_reaction(_phone, _msg_id, "⏳"))
            except Exception as e:
                api_logger.debug(f"WuzAPI reaction init failed: {e}")

        hermes_result = await invoke_hermes(
            urn=user_id,
            persona=model_persona,
            message=last_user_message,
            system_prompt=system_prompt_override,
            rivebot_context=rivebot_context,
            persona_vars=persona_vars,
            allowed_tools=persona_vars.get("allowed_tools"),
        )
        final_text = hermes_result.get("final_response", "")

        # Clear the hourglass
        if _phone and _msg_id:
            try:
                from app.api.middleware.wuzapi_client import send_reaction
                asyncio.create_task(send_reaction(_phone, _msg_id, ""))
            except Exception:
                pass

    except Exception as e:
        # ── AI failure: auto-enable noai mode ─────────────────────────────────
        api_logger.error(f"Hermes failed for {user_id}: {e}")
        
        # Clear the hourglass on failure
        try:
            if '_phone' in locals() and '_msg_id' in locals() and _phone and _msg_id:
                from app.api.middleware.wuzapi_client import send_reaction
                asyncio.create_task(send_reaction(_phone, _msg_id, ""))
        except Exception:
            pass

        await set_var(model_persona, user_id, "noai", "true")

        # Return the first noai message directly (don't wait for next match)
        lang = rivebot_context.get("lang", "ht")
        if lang == "en":
            noai_msg = (
                "⚠️ Our AI service is temporarily unavailable. We're working on it. "
                "In the meantime, type *help* to see what I can do for you."
            )
        else:
            noai_msg = (
                "⚠️ Sèvis AI nou an pa disponib pou kounye a. N ap travay sou sa. "
                "Antretan, tape *help* pou wè sa m ka fè pou ou."
            )
        return _openai_response(model_persona, noai_msg, id_prefix="chatcmpl-noai")

    # ── 5.1 AI succeeded: clear noai if it was previously set ─────────────────
    if rivebot_context.get("noai"):
        await set_var(model_persona, user_id, "noai", "false")
        api_logger.info(f"AI recovered for {user_id} — cleared noai flag")

    # ── 5.2 Persistence (fire-and-forget — F-08) ─────────────────────────
    # Palace write runs in background to avoid blocking the HTTP response.
    if not getattr(final_text, "skip_persistence", False):
        from app.hooks.palace_writer import persist_turn_to_palace

        async def _safe_persist():
            try:
                await asyncio.to_thread(
                    persist_turn_to_palace,
                    urn=user_id,
                    persona=model_persona,
                    user_message=last_user_message,
                    assistant_response=final_text,
                )
            except Exception as e:
                api_logger.warning(f"Background palace write failed: {e}")

        asyncio.create_task(_safe_persist())

    # ── 5.5 Advance RiveBot topic using tool metadata (F-23) ──────────────────
    from app.api.middleware.rivebot_client import (
        advance_topic_if_needed,
        STAGE_TRANSITIONS,
    )
    
    _hermes_messages = hermes_result.get("messages", [])
    _invoked_tools = [
        tc.get("function", {}).get("name") 
        for m in _hermes_messages if isinstance(m, dict) and m.get("tool_calls")
        for tc in m.get("tool_calls", [])
    ]
    # Fallback to string-matching if metadata is missing/incomplete
    _mentioned_tools = [t for t in STAGE_TRANSITIONS if t in (final_text or "")]
    _target_tools = set(_invoked_tools + _mentioned_tools)

    for tool_name in STAGE_TRANSITIONS:
        if tool_name in _target_tools:
            api_logger.info(f"Stage transition tool '{tool_name}' detected. Evaluating advancement.")
            await advance_topic_if_needed(tool_name, model_persona, user_id)
            break

    # Since Hermes returns just text, we don't have token counts easily accessible yet.
    # Set them to 0 or extract them later if Hermes adds usage tracking.
    prompt_tokens, completion_tokens = 0, 0

    return _openai_response(
        model_persona, final_text, prompt_tokens, completion_tokens
    )
