import os
import json
import logging
from typing import Dict, Any, Optional

try:
    from temba_client.v2 import TembaClient
except ImportError:
    # Fallback for dev/test environments without the library
    TembaClient = None

logger = logging.getLogger(__name__)

def get_client() -> Optional[Any]:
    """
    Factory to get the RapidPro client with environment variables.
    """
    host = os.getenv("RAPIDPRO_HOST")
    token = os.getenv("RAPIDPRO_API_TOKEN") # Note: Check .env if this name matches
    
    if not host or not token:
        logger.warning("RapidPro host/token not configured.")
        return None
        
    if not TembaClient:
        logger.error("temba_client library not installed.")
        return None

    return TembaClient(host, token)

def fetch_dossier(args: dict, **kwargs) -> str:
    """
    Fetch the user's official profile (Name, District, Language) from RapidPro.
    Use this at the START of a conversation to populate the Dossier.
    """
    urn = args.get("urn", "")
    if not urn:
        return json.dumps({"error": "No URN provided"})

    client = get_client()
    if not client:
        return json.dumps({"error": "RapidPro client unavailable"})

    try:
        contact = client.get_contacts(urn=urn).first()
        if not contact:
            return json.dumps({"error": "Contact not found in RapidPro"})
        
        return json.dumps({
            "name": contact.name,
            "language": contact.language,
            "uuid": contact.uuid,
            "fields": contact.fields or {}
        })
    except Exception as e:
        logger.error(f"Failed to fetch dossier for {urn}: {e}")
        return json.dumps({"error": str(e)})

def start_flow(args: dict, **kwargs) -> str:
    """Trigger a specific RapidPro flow for the user."""
    from app.graph.prompts import FLOW_REGISTRY
    
    urn = args.get("urn", "")
    flow_identifier = args.get("flow_identifier", "")

    if not urn or not flow_identifier:
        return json.dumps({"error": "Missing urn or flow_identifier"})
    
    client = get_client()
    if not client:
        return json.dumps({"error": "RapidPro client unavailable"})

    # Resolve Name -> UUID
    flow_uuid = FLOW_REGISTRY.get(flow_identifier, flow_identifier)

    try:
        client.create_flow_start(flow=flow_uuid, contacts=[urn])
        return json.dumps({"status": "success", "message": f"Flow '{flow_identifier}' (UUID: {flow_uuid}) started successfully."})
    except Exception as e:
        logger.error(f"Failed to start flow {flow_uuid} for {urn}: {e}")
        return json.dumps({"error": f"Failed to start flow: {e}"})


def start_crm_ops(args: dict, **kwargs) -> str:
    """Start the CRM operations flow for the admin user (ADR-010).

    Triggered by RiveBot's admin.rive via macro_bridge. Returns {{noreply}}
    to suppress the AI Gateway response — the RapidPro flow takes over the
    WhatsApp session entirely.

    The flow itself enforces authorization via a has_group(Admins) guard node.
    """
    # macro_bridge injects the URN as user_id via X-User-Id header
    urn = args.get("user_id", "")
    if not urn:
        return json.dumps({"error": "Missing user context."})

    # Ensure URN has a scheme prefix
    if ":" not in urn:
        urn = f"whatsapp:{urn}"

    flow_uuid = os.getenv("CRM_ROUTER_FLOW_UUID") or os.getenv("CRM_OPS_FLOW_UUID")
    if not flow_uuid:
        logger.error("[crm_ops] CRM_ROUTER_FLOW_UUID not configured")
        return "⚠️ CRM operations not configured. Set CRM_ROUTER_FLOW_UUID."

    client = get_client()
    if not client:
        return json.dumps({"error": "RapidPro client unavailable"})

    try:
        client.create_flow_start(
            flow=flow_uuid,
            urns=[urn],
            exclude_active=False,  # MUST interrupt existing session (Finding 6)
        )
        logger.info(f"[crm_ops] Started CRM ops flow for {urn}")
        return "{{noreply}}"  # Suppress AI response — flow sends its own menu
    except Exception as e:
        logger.error(f"[crm_ops] Failed to start CRM ops for {urn}: {e}")
        return f"⚠️ Failed to start CRM ops: {e}"


def send_crm_help(args: dict, **kwargs) -> str:
    """Send a WhatsApp Quick Reply button explaining how to access CRM ops (ADR-010 Layer A).

    Triggered by discovery phrases in admin.rive (e.g. "how do I manage contacts").
    Sends a tappable button via WuzAPI so the admin can activate the CRM flow
    without remembering the exact trigger text.

    Falls back to plain text if WuzAPI is unavailable.
    Returns {{noreply}} so the AI Gateway suppresses its own response.
    """
    urn = args.get("user_id", "")
    # Strip scheme prefix to get raw phone digits for WuzAPI
    phone = urn.split(":")[-1].lstrip("+") if urn else ""

    buttons = [{"DisplayText": "ops menu", "Type": "quickreply"}]
    msg = "🗂️ To open CRM Operations, tap the button below or type *ops menu* at any time."
    footer = "Tap to activate · Type 'exit_ops' to leave"

    if phone and os.getenv("WUZAPI_TOKEN"):
        from app.api.middleware.wuzapi_client import send_buttons
        import asyncio
        import concurrent.futures

        def _run_async():
            return asyncio.run(send_buttons(phone=phone, content=msg, footer=footer, buttons=buttons))

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                success = pool.submit(_run_async).result(timeout=6.0)
            if success:
                logger.info(f"[crm_help] Button message sent to {phone}")
                return "{{noreply}}"
        except Exception as e:
            logger.warning(f"[crm_help] WuzAPI button send failed: {e}")

    # Plain text fallback (no WuzAPI or send failed)
    logger.info(f"[crm_help] Fallback plain-text for {urn}")
    return "🗂️ Type *ops menu* to access CRM Operations, or *exit_ops* to leave a session."

