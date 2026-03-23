"""
Admin command: /broadcast

Send a message to all active users or a specific user
via RapidPro's Flow Start API.

Commands:
    /broadcast <message>              — send to all known active users
    /broadcast +509... <message>      — send to a specific contact

Requires:
    RAPIDPRO_URL and RAPIDPRO_TOKEN environment variables.
    A pre-configured RapidPro flow that accepts a @fields.message variable.
    RAPIDPRO_BROADCAST_FLOW_UUID environment variable.
"""
import os
import httpx
import logging
from .registry import CommandRegistry, CommandContext

logger = logging.getLogger("konex_commands")

RAPIDPRO_URL = os.getenv("RAPIDPRO_URL", "http://localhost:8000")
RAPIDPRO_TOKEN = os.getenv("RAPIDPRO_TOKEN", "")
BROADCAST_FLOW_UUID = os.getenv("RAPIDPRO_BROADCAST_FLOW_UUID", "")


async def _start_flow(urns: list[str], message: str) -> bool:
    """Trigger a RapidPro broadcast flow for a list of URNs."""
    if not RAPIDPRO_TOKEN or not BROADCAST_FLOW_UUID:
        raise ValueError(
            "RAPIDPRO_TOKEN and RAPIDPRO_BROADCAST_FLOW_UUID must be set"
        )
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{RAPIDPRO_URL}/api/v2/flow_starts.json",
            headers={
                "Authorization": f"Token {RAPIDPRO_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "flow": BROADCAST_FLOW_UUID,
                "urns": urns,
                "extra": {"message": message},
            },
        )
        resp.raise_for_status()
        return True


@CommandRegistry.register("broadcast")
async def cmd_broadcast(ctx: CommandContext) -> str:
    """/broadcast [+509xxx] <message> — send to one or all active users."""
    from app.api.middleware.rivebot_client import RIVEBOT_URL
    import httpx as _httpx

    if not ctx.args:
        return "⚠️ Usage: `/broadcast <message>` or `/broadcast +509xxx <message>`"

    # Detect if first arg looks like a phone number
    if ctx.args[0].startswith("+") or ctx.args[0].replace(" ", "").isdigit():
        target_num = ctx.args[0].lstrip("+")
        target_urns = [f"whatsapp:{target_num}"]
        message = " ".join(ctx.args[1:])
        if not message:
            return "⚠️ Usage: `/broadcast +509xxx <message>`"
        scope = f"1 contact ({ctx.args[0]})"
    else:
        # Fetch all known active users from RiveBot
        message = " ".join(ctx.args)
        try:
            async with _httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{RIVEBOT_URL}/stale-sessions?max_age_hours=720")
                # Collect all user_ids that have ever been active
                active_resp = await client.get(f"{RIVEBOT_URL}/noai-status")
                all_known: set[str] = set()
                if active_resp.status_code == 200:
                    data = active_resp.json()
                    for _, users in data.get("users", {}).items():
                        all_known.update(users)
            # Fall back to a broadcast to all if we can't enumerate
            if not all_known:
                return (
                    "⚠️ No active users found in RiveBot. "
                    "Users must have chatted at least once. "
                    "Or specify a number: `/broadcast +509xxx <message>`"
                )
            target_urns = [
                f"whatsapp:{uid.lstrip('whatsapp:')}" if not uid.startswith("whatsapp:") else uid
                for uid in all_known
            ]
            scope = f"{len(target_urns)} users"
        except Exception as e:
            return f"❌ Could not fetch users from RiveBot: {e}"

    try:
        await _start_flow(target_urns, message)
        logger.info(f"[broadcast] {ctx.user_id} → {scope}: {message[:50]}")
        return f"✅ Broadcast sent to {scope}:\n_{message}_"
    except ValueError as e:
        return f"❌ Config missing: {e}"
    except httpx.HTTPStatusError as e:
        return f"❌ RapidPro error {e.response.status_code}: {e.response.text[:100]}"
    except Exception as e:
        return f"❌ Broadcast failed: {e}"
