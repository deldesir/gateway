"""
Admin commands for toggling AI availability.

Commands:
    /noai           — disable AI for the current user
    /noai all       — disable AI for ALL users globally
    /noai status    — show current noai state
    /enableai       — re-enable AI for the current user
    /enableai all   — re-enable AI for ALL users globally
"""
from .registry import CommandRegistry, CommandContext
from app.api.middleware.rivebot_client import set_var
import logging

logger = logging.getLogger("konex_commands")


@CommandRegistry.register("noai")
async def cmd_noai(ctx: CommandContext) -> str:
    """Disable AI — deterministic triggers keep working."""
    scope = ctx.args[0].lower() if ctx.args else "self"

    if scope == "status":
        # Query RiveBot for noai status
        try:
            import httpx
            rivebot_url = "http://127.0.0.1:8087"
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{rivebot_url}/noai-status")
                if resp.status_code == 200:
                    data = resp.json()
                    global_flag = "🔴 ON" if data.get("global") else "🟢 OFF"
                    lines = [f"🔍 **NoAI Status**\n\nGlobal: {global_flag}"]
                    users = data.get("users", {})
                    if users:
                        for persona, uids in users.items():
                            lines.append(f"\n*{persona}*: {', '.join(uids)}")
                    else:
                        lines.append("\nNo individual users have noai set.")
                    return "\n".join(lines)
                return f"❌ RiveBot returned {resp.status_code}"
        except Exception as e:
            return f"❌ Could not reach RiveBot: {e}"

    elif scope == "all":
        await set_var("*", "*", "noai", "true")
        logger.warning(f"[noai] GLOBAL disable by {ctx.user_id}")
        return (
            "🔇 AI désaktive pou tout itilizatè yo.\n"
            "Tape */enableai all* pou reaktive l."
        )
    else:
        await set_var(ctx.persona, ctx.user_id, "noai", "true")
        logger.info(f"[noai] Disabled for {ctx.user_id} on {ctx.persona}")
        return (
            "🔇 AI désaktive pou ou.\n"
            "Tape */enableai* pou reaktive l."
        )


@CommandRegistry.register("enableai")
async def cmd_enableai(ctx: CommandContext) -> str:
    """Re-enable AI and reset the escalation counter."""
    scope = ctx.args[0].lower() if ctx.args else "self"

    if scope == "all":
        await set_var("*", "*", "noai", "false")
        logger.info(f"[noai] GLOBAL re-enable by {ctx.user_id}")
        return "✅ AI reaktive pou tout itilizatè yo."
    else:
        await set_var(ctx.persona, ctx.user_id, "noai", "false")
        logger.info(f"[noai] Re-enabled for {ctx.user_id} on {ctx.persona}")
        return "✅ AI reaktive pou ou."
