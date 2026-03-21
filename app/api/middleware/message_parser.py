"""
Message parsing utilities for the OpenAI-compatible endpoint.

RapidPro sends messages in the format::

    "Name (whatsapp:+1234 > 5678) says: Hello"

This module extracts the URN, optional channel ID, and clean message
content from that prefix, making the rest of the handler clean.
"""

import re
from dataclasses import dataclass
from typing import Optional

# RapidPro URN prefix: "Name (urn > channel) says: content"
_URN_SIMPLE = re.compile(r"(tel|whatsapp|telegram):(\+?\d+)")
_URN_PREFIX = re.compile(
    r"^.*?\("
    r"(?P<urn>(?:(?:tel|whatsapp|telegram):)?\+?\d+)"
    r"(?:\s*>\s*(?P<channel>\+?\d+))?"
    r"\) says:\s+"
)


@dataclass
class ParsedMessage:
    content: str              # cleaned message, prefix stripped
    user_id: Optional[str]   # e.g. "whatsapp:+12345"
    channel_id: Optional[str] # e.g. "5678" (maps to a persona)


def parse_rapidpro_message(raw: str, user_hint: Optional[str] = None) -> ParsedMessage:
    """Extract URN, channel, and clean content from a RapidPro message.

    Args:
        raw: Raw message content from RapidPro.
        user_hint: Explicit user ID from the ``user`` JSON field (may be None).

    Returns:
        ParsedMessage with content, user_id, and channel_id.
    """
    user_id = user_hint
    channel_id = None
    content = raw

    # 1. Try the simple URN pattern first (e.g. in bare messages)
    if not user_id:
        m = _URN_SIMPLE.search(raw)
        if m:
            user_id = f"{m.group(1)}:{m.group(2)}"

    # 2. Try the full RapidPro prefix pattern
    m = _URN_PREFIX.search(raw)
    if m:
        content = _URN_PREFIX.sub("", raw, count=1)
        if not user_id and m.group("urn"):
            user_id = m.group("urn")
        if m.group("channel"):
            channel_id = m.group("channel").lstrip("+")

    return ParsedMessage(content=content, user_id=user_id, channel_id=channel_id)
