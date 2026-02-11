import os
import logging
from typing import Dict, Any, Optional

from langchain_core.tools import tool
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

@tool
def fetch_dossier(urn: str) -> Dict[str, Any]:
    """
    Fetch the user's official profile (Name, District, Language) from RapidPro.
    Use this at the START of a conversation to populate the Dossier.
    
    Args:
        urn (str): The user's URN (e.g., "whatsapp:1234567890").
    """
    client = get_client()
    if not client:
        return {}

    try:
        # RapidPro uses URNs like "whatsapp:..."
        # We need to handle potential errors gracefully
        contact = client.get_contacts(urn=urn).first()
        if not contact:
            return {}
        
        return {
            "name": contact.name,
            "language": contact.language,
            "uuid": contact.uuid,
            "fields": contact.fields or {}
        }
    except Exception as e:
        logger.error(f"Failed to fetch dossier for {urn}: {e}")
        return {}

@tool
def start_flow(urn: str, flow_identifier: str) -> str:
    """
    Trigger a specific RapidPro flow for the user.
    
    Args:
        urn (str): The user's URN.
        flow_identifier (str): The Name OR UUID of the flow to start.
    """
    # Import here to avoid circular dependencies if any
    from app.graph.prompts import FLOW_REGISTRY
    
    client = get_client()
    if not client:
        return "RapidPro client unavailable."

    # Resolve Name -> UUID
    flow_uuid = FLOW_REGISTRY.get(flow_identifier, flow_identifier)

    try:
        client.create_flow_start(flow=flow_uuid, contacts=[urn])
        return f"Flow '{flow_identifier}' (UUID: {flow_uuid}) started successfully."
    except Exception as e:
        logger.error(f"Failed to start flow {flow_uuid} for {urn}: {e}")
        return f"Failed to start flow: {e}"
