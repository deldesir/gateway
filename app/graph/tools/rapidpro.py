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
