import os
import httpx
from .registry import CommandRegistry, CommandContext


@CommandRegistry.register("reload")
async def cmd_reload(ctx: CommandContext) -> str:
    """Trigger a RiveBot brain reload. Usage: #reload"""
    rivebot_url = os.getenv("RIVEBOT_URL", "http://localhost:8785")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{rivebot_url}/reload")
            data = resp.json()
        reloaded = data.get("reloaded", [])
        return (
            f"✅ RiveBot brains reloaded!\n"
            f"• Engines: {', '.join(reloaded) if reloaded else 'none'}\n"
            f"• Count: {len(reloaded)}"
        )
    except Exception as e:
        return f"❌ Reload failed: {e}"
