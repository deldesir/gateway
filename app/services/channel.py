from sqlmodel import select
from app.db import get_session
from app.models import ChannelConfig, Persona
from app.logger import logger

api_logger = logger.bind(name="ChannelService")

async def resolve_persona(channel_phone: str) -> tuple[str, str | None]:
    """
    Resolve the configured Persona ID and optional System Prompt Override 
    for a given Channel Phone Number.
    
    Returns:
        (persona_id, system_prompt_override)
        If no channel config found, returns (channel_phone, None) - treating input as potential persona.
    """
    # 1. Try exact match on channel phone
    try:
        async for session in get_session():
            query = select(ChannelConfig).where(ChannelConfig.channel_phone == channel_phone)
            result = await session.exec(query)
            channel_config = result.first()
            
            if channel_config:
                # Found config, verify mapped persona exists
                persona = await session.get(Persona, channel_config.persona_id)
                if persona:
                    api_logger.info(f"Mapped Channel '{channel_phone}' -> Persona '{persona.name}' ({persona.id})")
                    return persona.id, channel_config.system_prompt_override
                else:
                    api_logger.warning(f"Channel Config found for '{channel_phone}' but Persona ID '{channel_config.persona_id}' missing.")
            else:
                # No config found
                pass
            break 
    except Exception as e:
        api_logger.error(f"Error resolving persona: {e}")
        
    # Default fallthrough: Assume the input might be the persona ID itself (legacy behavior)
    return channel_phone, None
