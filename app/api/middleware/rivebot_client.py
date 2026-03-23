"""
RiveBot HTTP client — called from the AI Gateway to:
  1. Pre-match messages before LangGraph (match_intent)
  2. Advance a user's workflow topic when a stage-completing tool runs (set_topic)
"""

import os
from typing import Optional

import httpx
from loguru import logger

RIVEBOT_URL = os.getenv("RIVEBOT_URL", "http://127.0.0.1:8087")

# Tools that complete a workflow stage mapped to the topic they unlock.
# Mirrors STAGE_TRANSITIONS in rivebot/macro_bridge.py — keep in sync.
STAGE_TRANSITIONS: dict[str, str] = {
    "import_talk":         "stage_1",
    "select_active_talk":  "stage_1",
    "create_revision":     "stage_2",
    "develop_section":     "stage_3",
    "evaluate_talk":       "stage_4",
    "rehearsal_cue":       "stage_5",
    "export_talk_summary": "stage_6",
}

_TOPIC_ORDER = ["random", "stage_1", "stage_2", "stage_3", "stage_4", "stage_5", "stage_6"]


async def match_intent(
    message: str, persona: str, user_id: str = "user"
) -> tuple[Optional[str], dict]:
    """
    Call RiveBot to attempt a deterministic match before invoking LangGraph.

    Returns:
        (response, context) where:
        - response: the reply string if matched, or None to fall through to AI
        - context:  session context dict from RiveBot (lang, topic, history)
                    Always returned, even on fallback, for AI continuity.
                    May contain "silent": True when noai 3rd+ fallback triggers.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{RIVEBOT_URL}/match",
                json={"message": message, "persona": persona, "user": user_id},
            )
            if resp.status_code == 200:
                data = resp.json()
                context = data.get("context", {})
                # Propagate silence flag from noai escalation
                if data.get("silent"):
                    context["silent"] = True
                if data.get("matched"):
                    return data.get("response"), context
                return None, context
        return None, {}
    except httpx.TimeoutException:
        logger.warning(f"[rivebot] Timeout reaching {RIVEBOT_URL}")
        return None, {}
    except Exception as e:
        logger.error(f"[rivebot] Error calling brain service: {e}")
        return None, {}


async def set_var(
    persona: str, user_id: str, var: str, value: str
) -> None:
    """Set a RiveScript user variable via RiveBot's /set-var endpoint.

    Fire-and-forget — never blocks the response pipeline.
    Used to toggle noai mode when AI fails or recovers.
    """
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.post(
                f"{RIVEBOT_URL}/set-var",
                json={"persona": persona, "user": user_id, "var": var, "value": value},
            )
            if resp.status_code == 200:
                logger.info("[rivebot] " + persona + ":" + user_id + " — set " + var + "=" + value)
            else:
                logger.warning(f"[rivebot] set-var returned {resp.status_code}: {resp.text[:80]}")
    except Exception as e:
        logger.warning(f"[rivebot] set-var failed (non-blocking): {e}")


async def advance_topic_if_needed(tool_name: str, persona: str, user_id: str) -> None:
    """
    If tool_name completes a workflow stage, advance the user's RiveScript topic.

    Called from openai.py after LangGraph completes, so that the user's next
    message to RiveBot is matched against the correct stage-locked triggers.
    Fires-and-forgets on error — never blocks the response.
    """
    next_topic = STAGE_TRANSITIONS.get(tool_name)
    if not next_topic:
        return

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.post(
                f"{RIVEBOT_URL}/set-topic",
                json={"persona": persona, "user": user_id, "topic": next_topic},
            )
            if resp.status_code == 200:
                logger.info(f"[rivebot] {user_id}: topic → {next_topic} (via {tool_name})")
            else:
                logger.warning(f"[rivebot] set-topic returned {resp.status_code}: {resp.text[:80]}")
    except Exception as e:
        logger.warning(f"[rivebot] set-topic failed (non-blocking): {e}")


def detect_stage_completing_tool(result: dict) -> Optional[str]:
    """
    Inspect a LangGraph result dict for tool messages and return the name
    of the last stage-completing tool that was called, or None.

    LangGraph stores tool call results as ToolMessage objects in result["messages"].
    Each ToolMessage has a .name attribute with the tool function name.
    """
    from langchain_core.messages import ToolMessage
    messages = result.get("messages", [])
    # Walk backwards to find the last stage-completing tool
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and msg.name in STAGE_TRANSITIONS:
            return msg.name
    return None
