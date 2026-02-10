from .registry import CommandRegistry, CommandContext
from app.db import get_session
from app.models import ChannelConfig, Persona
from sqlmodel import select

@CommandRegistry.register("channel")
async def cmd_channel(ctx: CommandContext) -> str:
    """Manages channel-persona mapping. Usage: #channel <assign|list> ..."""
    if not ctx.args:
        return "⚠️ Usage: `#channel assign <phone> <persona_name>`, `#channel list`"
        
    action = ctx.args[0].lower()
    
    if action == "assign":
        if len(ctx.args) < 3:
            return "⚠️ Usage: `#channel assign <phone> <persona_name>`"
            
        phone = ctx.args[1]
        persona_name = ctx.args[2]
        
        async for session in get_session():
            # 1. Find Persona
            p_result = await session.exec(select(Persona).where(Persona.name == persona_name))
            persona = p_result.first()
            if not persona:
                return f"❌ Persona `{persona_name}` not found. Create it first with `#persona create`."
            
            # 2. Find/Create Channel Config
            c_result = await session.exec(select(ChannelConfig).where(ChannelConfig.channel_phone == phone))
            config = c_result.first()
            
            if config:
                config.persona_id = persona.id
                session.add(config)
                msg = f"✅ Updated channel `{phone}` -> Persona `{persona.name}`."
            else:
                config = ChannelConfig(channel_phone=phone, persona_id=persona.id)
                session.add(config)
                msg = f"✅ Assigned channel `{phone}` -> Persona `{persona.name}`."
                
            await session.commit()
            return msg

    elif action == "list":
        async for session in get_session():
            # Join with Persona to get names
            # SQLModel doesn't support joinedload nicely in async without explicit join or separate query
            # Let's just list IDs or lookups.
            # Actually, let's do a join if possible or just loop. Loop is fine for small N.
            
            configs = (await session.exec(select(ChannelConfig))).all()
            if not configs:
                return "📭 No channel configurations found."
            
            msg = "📡 **Channel Configs**:\n"
            for c in configs:
                # Fetch persona name
                p_res = await session.get(Persona, c.persona_id)
                p_name = p_res.name if p_res else  "Unknown (Deleted?)"
                msg += f"- `{c.channel_phone}` -> `{p_name}`\n"
            return msg
            
    return f"❌ Unknown action: {action}"
