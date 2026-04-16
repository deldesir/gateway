"""
V2 Hermes Engine — invokes Hermes Agent as an in-process library.

Design constraints (from architecture_v2_design.md):
  - 800MB memory ceiling (systemd MemoryMax)
  - Edge hardware: 2–4 GB RAM, single-digit cores
  - WhatsApp-only interface via RapidPro → OpenAI adapter
  - Must coexist with RiveBot deterministic router + admin commands

The engine wraps AIAgent.chat() in a thread pool because Hermes is
synchronous (blocking network calls to LLM providers). The async
FastAPI handler offloads each invocation to the pool, freeing the
event loop for concurrent WhatsApp messages.

Burst protection:
  - _in_flight TTL dedup: prevents duplicate processing of the same
    message when WhatsApp retries (common on spotty connectivity)
  - Queue depth limiting: rejects messages when the thread pool is
    saturated rather than OOMing with queued work
"""

import asyncio
import contextvars
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any

from run_agent import AIAgent

logger = logging.getLogger(__name__)

# ── Configuration (from environment, set by Ansible templates) ──────────────

_MAX_WORKERS = int(os.getenv("HERMES_THREAD_POOL_SIZE", "2"))
_MAX_ITERATIONS = int(os.getenv("HERMES_MAX_ITERATIONS", "15"))
_DEDUP_TTL = int(os.getenv("HERMES_DEDUP_TTL", "30"))    # seconds
_MAX_QUEUE_DEPTH = int(os.getenv("HERMES_MAX_QUEUE", "4"))
_RATE_LIMIT_SECS = float(os.getenv("HERMES_RATE_LIMIT_SECS", "5.0"))

# ── Thread pool ─────────────────────────────────────────────────────────────

_pool = ThreadPoolExecutor(
    max_workers=_MAX_WORKERS,
    thread_name_prefix="hermes",
)

# ── Context variable for tenant isolation ────────────────────────────────────
# Server-side injection prevents prompt-injection attacks that try to
# switch wing context via crafted messages.

_current_urn: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_current_urn", default=""
)

# ── Burst protection state ──────────────────────────────────────────────────

# {message_hash: (timestamp, future)} — prevents duplicate processing
_in_flight: Dict[str, tuple] = {}

# Current number of queued/running tasks
_queue_depth = 0

# Per-URN rate limiting (§11.3): {urn: monotonic_timestamp}
_last_cognitive: Dict[str, float] = {}


def _message_key(urn: str, message: str) -> str:
    """Deterministic dedup key for a user+message pair."""
    return f"{urn}:{hash(message)}"


def _cleanup_expired() -> None:
    """Remove expired dedup entries (called before each invocation)."""
    now = time.monotonic()
    expired = [k for k, (ts, _) in _in_flight.items() if now - ts > _DEDUP_TTL]
    for k in expired:
        _in_flight.pop(k, None)


def _build_system_prompt(
    persona_vars: dict,
    system_prompt_override: Optional[str] = None,
    rivebot_context: Optional[dict] = None,
) -> str:
    """
    Build the system prompt for Hermes from persona DB fields.

    This replicates the CHARACTER_CARD template from V1's prompts.py,
    translating it into a flat string that Hermes understands as its
    ephemeral system prompt.
    """
    parts = []

    name = persona_vars.get("persona_name", "Assistant")
    personality = persona_vars.get("persona_personality", "")
    style = persona_vars.get("persona_style", "")

    parts.append(f"You are {name}.")
    if personality:
        parts.append(f"Personality: {personality}")
    if style:
        parts.append(f"Communication style: {style}")

    if system_prompt_override:
        parts.append(f"\nAdditional instructions:\n{system_prompt_override}")

    # Inject RiveBot context (language, user name, onboarding state)
    if rivebot_context:
        lang = rivebot_context.get("lang", "ht")
        user_name = rivebot_context.get("name")
        if lang:
            parts.append(f"\nUser's preferred language: {lang}")
        if user_name and user_name != "undefined":
            parts.append(f"User's name: {user_name}")

    return "\n".join(parts)


def _invoke_sync(
    urn: str,
    persona: str,
    message: str,
    system_prompt: str,
    model: Optional[str] = None,
) -> str:
    """
    Synchronous Hermes invocation — runs in the thread pool.

    Creates a fresh AIAgent per call (lightweight, no persistent state).
    Hermes manages its own session/memory internally via HERMES_HOME.
    """
    # Set context var for tenant isolation (used by MemPalace tools)
    _current_urn.set(urn)

    agent = AIAgent(
        model=model or os.getenv("LLM_MODEL", ""),
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
        max_iterations=_MAX_ITERATIONS,
        enabled_toolsets=[
            "rapidpro", 
            "mocks", 
            "forms", 
            "upload", 
            "talkprep", 
            "mempalace", 
            "session_search", 
            "clarify"
        ],
        ephemeral_system_prompt=system_prompt,
        session_id=f"whatsapp:{urn}:{persona}",
        user_id=urn,
        platform="whatsapp",
        quiet_mode=True,
        skip_context_files=True,   # No project context on edge device
        skip_memory=True,          # We use MemPalace, not built-in USER.md
        verbose_logging=False,
    )

    result = agent.chat(message)
    return result


async def invoke_hermes(
    urn: str,
    persona: str,
    message: str,
    system_prompt: Optional[str] = None,
    rivebot_context: Optional[dict] = None,
    persona_vars: Optional[dict] = None,
) -> str:
    """
    Async entry point for the V2 engine — called from openai.py.

    Args:
        urn: WhatsApp URN (e.g. "whatsapp:+50937...")
        persona: Persona slug (e.g. "konex-support")
        message: User's message text
        system_prompt: Optional override from channel config
        rivebot_context: Dict from RiveBot intent matching
        persona_vars: Dict from PersonaPromptRegistry.get_async()

    Returns:
        str: Assistant response text

    Raises:
        RuntimeError: If queue is full (burst protection)
    """
    global _queue_depth

    # ── Dedup check ──────────────────────────────────────────────────────
    _cleanup_expired()
    key = _message_key(urn, message)

    if key in _in_flight:
        ts, future = _in_flight[key]
        logger.info(f"Dedup hit for {urn} — reusing in-flight result")
        if future.done():
            return future.result()
        # Wait for the existing invocation to complete
        return await asyncio.wrap_future(future)

    # ── Per-URN rate limit (§11.3) ────────────────────────────────────────
    now = time.monotonic()
    if now - _last_cognitive.get(urn, 0) < _RATE_LIMIT_SECS:
        logger.info(f"Rate limit hit for {urn} — throttling")
        return "Please wait a few seconds before sending another message."
    _last_cognitive[urn] = now

    # ── Queue depth check ────────────────────────────────────────────────
    if _queue_depth >= _MAX_QUEUE_DEPTH:
        logger.warning(f"Queue full ({_queue_depth}/{_MAX_QUEUE_DEPTH}) — rejecting {urn}")
        raise RuntimeError("Service busy — please try again in a moment.")

    # ── Build system prompt ──────────────────────────────────────────────
    full_prompt = _build_system_prompt(
        persona_vars=persona_vars or {},
        system_prompt_override=system_prompt,
        rivebot_context=rivebot_context,
    )

    # ── Submit to thread pool ────────────────────────────────────────────
    _queue_depth += 1
    ctx = contextvars.copy_context()

    try:
        future = _pool.submit(
            ctx.run,
            _invoke_sync,
            urn, persona, message, full_prompt,
        )
        _in_flight[key] = (time.monotonic(), future)

        result = await asyncio.wrap_future(future)
        return result

    finally:
        _queue_depth -= 1
        # Clean up dedup entry after completion
        _in_flight.pop(key, None)
