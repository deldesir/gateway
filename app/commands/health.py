import os
import httpx
from .registry import CommandRegistry, CommandContext


@CommandRegistry.register("health")
async def cmd_health(ctx: CommandContext) -> str:
    """Check health of ecosystem services. Usage: #health"""
    services = {
        "RiveBot": os.getenv("RIVEBOT_URL", "http://localhost:8785") + "/health",
        "AI Gateway": "http://localhost:8086/health",
    }

    # Optional services — only check if configured
    siyuan_url = os.getenv("SIYUAN_API_URL")
    if siyuan_url:
        services["SiYuan"] = f"{siyuan_url}/api/system/version"

    lines = ["🏥 *System Health Check*\n"]
    all_ok = True

    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in services.items():
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    lines.append(f"✅ **{name}**: OK")
                else:
                    lines.append(f"⚠️ **{name}**: HTTP {resp.status_code}")
                    all_ok = False
            except Exception as e:
                lines.append(f"❌ **{name}**: {e}")
                all_ok = False

    if all_ok:
        lines.append("\n🟢 All services healthy.")
    else:
        lines.append("\n🔴 Some services need attention.")

    return "\n".join(lines)
