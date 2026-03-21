"""
Deterministic intent router — intercepts well-known intents BEFORE the LangGraph.

Design principle: if a computer can compute the exact right answer, AI must not
be involved. This router pattern-matches the cleaned message against a table of
known intents per persona and calls the underlying function directly — zero LLM
tokens, zero latency from model inference.

Falls through (returns None) when no pattern matches, letting LangGraph handle
the request normally.

Pattern format: compiled regex, checked case-insensitively against the full
cleaned message. First match wins (order matters — more specific first).

Multilingual: patterns cover English, French, and Haitian Creole equivalents
so users get instant responses regardless of which language they use.
"""

import asyncio
import re
from typing import Callable, Optional
from app.logger import setup_logger

logger = setup_logger().bind(name="intent_router")


# ── Intent table type ─────────────────────────────────────────────────────────
#  Each entry: (compiled_regex, async_handler)
#  Handler signature: async (user_id: str, message: str) -> str

type IntentEntry = tuple[re.Pattern, Callable]


# ── TalkPrep direct handlers (bypass LangGraph) ───────────────────────────────

async def _intent_status(user_id: str, message: str) -> str:
    from app.graph.tools.talkprep import talkmaster_status
    return await talkmaster_status.ainvoke({})


async def _intent_help(user_id: str, message: str) -> str:
    from app.graph.tools.talkprep import get_talkprep_help
    return await get_talkprep_help.ainvoke({})


async def _intent_publications(user_id: str, message: str) -> str:
    from app.graph.tools.talkprep import list_publications
    return await list_publications.ainvoke({})


async def _intent_cost(user_id: str, message: str) -> str:
    from app.graph.tools.talkprep import cost_report
    return await cost_report.ainvoke({})


# ── Konex-Support direct handlers ─────────────────────────────────────────────

async def _intent_support_help(user_id: str, message: str) -> str:
    return (
        "👋 *Konex Support — Commands disponib:*\n\n"
        "• `#profile` — wè enfòmasyon kont ou\n"
        "• `#reset` — efase istwa konvèsasyon an\n"
        "• `#help` — afiche tout kòmand yo\n\n"
        "Sinon, ekri mesaj ou a epi m ap reponn."
    )


# ── Intent tables per persona ─────────────────────────────────────────────────
# Pattern flags: IGNORECASE applied at match time

_TALKPREP_INTENTS: list[tuple[str, Callable]] = [
    # Status / show talks — EN + FR + HC
    (r"\b(status|my talks?|show talks?|montre talk|ki talk mwen|afiche talk|list(?: my)? talks?)\b",
     _intent_status),

    # Help / onboarding — EN + FR + HC
    (r"\b(help|aide|what can you do|kisa ou ka fè|kisa ou kapab|command[se]?|komand)\b",
     _intent_help),

    # Publications list — EN + FR + HC
    (r"\b(list pub|publications?|piblikasyon|what books?|ki liv|ki pub)\b",
     _intent_publications),

    # Cost / usage report — EN + FR + HC
    (r"\b(cost|usage|token[s]?(?:\s+used)?|how much|konbyen|depans|bilan|rapport coût)\b",
     _intent_cost),
]

_KONEX_SUPPORT_INTENTS: list[tuple[str, Callable]] = [
    (r"\b(help|aide|kisa ou ka|what can|command[s]?)\b", _intent_support_help),
]

_KONEX_SALES_INTENTS: list[tuple[str, Callable]] = []

# Registry: persona_id → compiled intent list
_REGISTRY: dict[str, list[tuple[re.Pattern, Callable]]] = {
    "talkprep": [
        (re.compile(pat, re.IGNORECASE), fn)
        for pat, fn in _TALKPREP_INTENTS
    ],
    "konex-support": [
        (re.compile(pat, re.IGNORECASE), fn)
        for pat, fn in _KONEX_SUPPORT_INTENTS
    ],
    "konex-sales": [],
}


# ── Public API ────────────────────────────────────────────────────────────────

class IntentRouter:
    """Pre-LLM deterministic intent dispatcher."""

    @classmethod
    async def dispatch(
        cls,
        message: str,
        persona: str,
        user_id: str,
    ) -> Optional[str]:
        """Try to handle the message deterministically.

        Args:
            message: Cleaned user message (RapidPro prefix already stripped).
            persona: Active persona ID (e.g. 'talkprep', 'konex-support').
            user_id: User's URN (for logging/context).

        Returns:
            Response string if a pattern matched, None to fall through to LangGraph.
        """
        intents = _REGISTRY.get(persona, [])
        stripped = message.strip()

        for pattern, handler in intents:
            if pattern.search(stripped):
                logger.info(
                    f"Intent matched | persona={persona} | "
                    f"pattern={pattern.pattern!r} | user={user_id}"
                )
                try:
                    return await handler(user_id, stripped)
                except Exception as e:
                    logger.error(f"Intent handler failed: {e}")
                    return None  # fall through to LangGraph on error

        return None  # no match
