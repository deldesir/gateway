"""
Form submission tool — receives data from RiveBot multi-turn forms.

Called via macro_bridge when a user confirms a form in RiveScript:
  <call>submit_form support My issue here</call>
  <call>submit_form upgrade premium +50937000001</call>

The first positional arg is the form type, the rest is the data.
"""

from langchain.tools import tool
from loguru import logger


@tool
async def submit_form(form_type: str, data: str, user_id: str = "unknown") -> str:
    """Submit a completed form from the RiveBot multi-turn flow.

    Args:
        form_type: The type of form (e.g., "support", "upgrade").
        data: The collected form data as a space-separated string.
        user_id: The user who submitted the form.

    Returns:
        A confirmation message for the user.
    """
    logger.info(f"[submit_form] type={form_type} user={user_id} data='{data}'")

    # ── Route by form type ──────────────────────────────────────
    if form_type == "support":
        # In production: create a ticket in the helpdesk system
        logger.info(f"[submit_form] Support ticket from {user_id}: {data}")
        return (
            "✅ Tiket sipò ou an soumèt avèk siksè! "
            "Nou pral kontakte w nan lè ki pi vit posib. 📋"
        )

    elif form_type == "upgrade":
        # In production: notify sales team or trigger a RapidPro flow
        parts = data.split(None, 1)
        plan = parts[0] if parts else "unknown"
        phone = parts[1] if len(parts) > 1 else "N/A"
        logger.info(
            f"[submit_form] Upgrade request from {user_id}: "
            f"plan={plan} phone={phone}"
        )
        return (
            f"✅ Demann pou plan *{plan}* soumèt! "
            "Ekip vant la pral kontakte w byento. 📞"
        )

    else:
        logger.warning(f"[submit_form] Unknown form type: {form_type}")
        return "✅ Fòmilè w la soumèt. Mèsi!"
