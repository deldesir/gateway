import os
import httpx
from loguru import logger
from typing import Optional

RIVEBOT_URL = os.getenv("RIVEBOT_URL", "http://127.0.0.1:8087")

async def match_intent(message: str, persona: str, user_id: str = "user") -> Optional[str]:
    """
    Call the external RiveScript brain service to attempt a deterministic match.
    Returns the response string if matched, or None to fall through to AI.
    """
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.post(
                f"{RIVEBOT_URL}/match",
                json={"message": message, "persona": persona, "user": user_id}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("matched"):
                    return data.get("response")
            return None
    except httpx.TimeoutException:
        logger.warning(f"[rivebot] Timeout reaching {RIVEBOT_URL}")
        return None
    except Exception as e:
        logger.error(f"[rivebot] Error calling brain service: {e}")
        return None
