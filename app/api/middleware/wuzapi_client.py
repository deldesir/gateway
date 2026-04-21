"""
WuzAPI client — direct API calls for WhatsApp features not available via RapidPro.

Currently supports:
- Message reactions (emoji on existing messages)
- Mark as read

WuzAPI docs: /opt/iiab/wuzapi/API.md
"""

import os
import logging
import httpx

logger = logging.getLogger("ai-gateway.wuzapi")

WUZAPI_URL = os.getenv("WUZAPI_URL", "http://localhost:8095")
WUZAPI_TOKEN = os.getenv("WUZAPI_TOKEN", "")


async def send_reaction(
    phone: str,
    message_id: str,
    emoji: str = "👍",
) -> bool:
    """React to a WhatsApp message with an emoji.

    Args:
        phone: Recipient phone number (digits only, e.g. "50942614949").
        message_id: WhatsApp message ID to react to.
        emoji: Emoji to react with (default: 👍).

    Returns:
        True if the reaction was sent successfully.
    """
    if not WUZAPI_TOKEN:
        logger.warning("WUZAPI_TOKEN not set — cannot send reaction")
        return False

    url = f"{WUZAPI_URL}/chat/react"
    payload = {"Phone": phone, "Body": emoji, "Id": message_id}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": WUZAPI_TOKEN},
            )
        if resp.status_code == 200:
            logger.info(f"Reaction {emoji} sent to {phone} on msg {message_id}")
            return True
        else:
            logger.warning(f"WuzAPI react failed: {resp.status_code} {resp.text[:100]}")
            return False
    except Exception as e:
        logger.warning(f"WuzAPI react error: {e}")
        return False


async def mark_as_read(phone: str, message_id: str) -> bool:
    """Mark a message as read (blue ticks).

    Args:
        phone: Sender phone number.
        message_id: WhatsApp message ID to mark as read.

    Returns:
        True if successful.
    """
    if not WUZAPI_TOKEN:
        return False

    url = f"{WUZAPI_URL}/chat/markread"
    payload = {"Id": message_id, "Chat": f"{phone}@s.whatsapp.net"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": WUZAPI_TOKEN},
            )
        return resp.status_code == 200
    except Exception:
        return False


async def send_buttons(
    phone: str,
    content: str,
    buttons: list[dict],
    footer: str = "",
) -> bool:
    """Send a WhatsApp message with Quick Reply buttons via WuzAPI (ADR-010 Layer A).

    Uses /chat/send/template (source-verified in /opt/iiab/wuzapi/API.md).

    Args:
        phone: Recipient phone number (digits only, e.g. "50937145893").
        content: Message body text.
        buttons: List of {"DisplayText": "text", "Type": "quickreply"}.
                 Max 3 buttons per WhatsApp and WuzAPI constraints.
        footer: Optional footer text (max 60 chars recommended).

    Returns:
        True if sent successfully.

    CRITICAL: The button's DisplayText is BOTH the label shown on the button AND
    the exact text WhatsApp sends as a message when the user taps it.
    It MUST match a RiveBot trigger in _common/admin.rive exactly (case-insensitive).
    """
    if not WUZAPI_TOKEN:
        logger.warning("WUZAPI_TOKEN not set — cannot send buttons")
        return False

    payload = {
        "Phone": phone,
        "Content": content,
        "Footer": footer,
        "Buttons": buttons[:3],  # WhatsApp hard cap: 3 quickreply buttons
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{WUZAPI_URL}/chat/send/template",
                json=payload,
                headers={"Authorization": WUZAPI_TOKEN},
            )
        if resp.status_code == 200:
            labels = [b.get("DisplayText", "?") for b in buttons]
            logger.info(f"Button message sent to {phone}: {labels}")
            return True
        else:
            logger.warning(f"WuzAPI button send failed: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.warning(f"WuzAPI button send error: {e}")
        return False

