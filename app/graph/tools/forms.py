import json
from loguru import logger


def submit_form(args: dict, **kwargs) -> str:
    """Submit a completed form from the RiveBot multi-turn flow."""
    form_type = args.get("form_type", "")
    data = args.get("data", "")
    user_id = args.get("user_id", "unknown")

    if not form_type or not data:
        return json.dumps({"error": "Missing form_type or data"})

    logger.info(f"[submit_form] type={form_type} user={user_id} data='{data}'")

    # ── Route by form type ──────────────────────────────────────
    if form_type == "support":
        # In production: create a ticket in the helpdesk system
        logger.info(f"[submit_form] Support ticket from {user_id}: {data}")
        return json.dumps({
            "status": "success",
            "message": "✅ Tiket sipò ou an soumèt avèk siksè! Nou pral kontakte w nan lè ki pi vit posib. 📋"
        })

    elif form_type == "upgrade":
        # In production: notify sales team or trigger a RapidPro flow
        parts = data.split(None, 1)
        plan = parts[0] if parts else "unknown"
        phone = parts[1] if len(parts) > 1 else "N/A"
        logger.info(
            f"[submit_form] Upgrade request from {user_id}: "
            f"plan={plan} phone={phone}"
        )
        return json.dumps({
            "status": "success",
            "message": f"✅ Demann pou plan *{plan}* soumèt! Ekip vant la pral kontakte w byento. 📞"
        })

    else:
        logger.warning(f"[submit_form] Unknown form type: {form_type}")
        return json.dumps({
            "status": "success",
            "message": "✅ Fòmilè w la soumèt. Mèsi!"
        })
