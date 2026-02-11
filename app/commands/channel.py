from .registry import CommandRegistry, CommandContext
from app.db import get_session
from app.models import ChannelConfig, Persona
from sqlmodel import select

@CommandRegistry.register("channel")
async def cmd_channel(ctx: CommandContext) -> str:
    """Manages channel-persona mapping. Usage: #channel <assign|set_instruction|list> ..."""
    if not ctx.args:
        return (
            "⚠️ **Usage**: `#channel <action> ...`\n"
            "- `assign <phone> <persona_id>`: Route a number to a persona.\n"
            "- `set_instruction <phone> <text>`: Set system prompt override.\n"
            "- `list`: Show all mappings."
        )
        
    action = ctx.args[0].lower()
    
    if action == "assign":
        if len(ctx.args) < 3:
            return "⚠️ Usage: `#channel assign <phone> <persona_name>`"
            
        phone = ctx.args[1]
        persona_name = ctx.args[2]
        
        async for session in get_session():
            # 1. Find Persona (Try Name first, then ID)
            p_result = await session.exec(select(Persona).where(Persona.name == persona_name))
            persona = p_result.first()
            
            if not persona:
                 # Try ID
                 p_result = await session.exec(select(Persona).where(Persona.id == persona_name))
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

            await session.commit()
            return msg

    elif action == "set_instruction":
        if len(ctx.args) < 3:
            return "⚠️ Usage: `#channel set_instruction <phone> <instruction_text>`"
            
        phone = ctx.args[1]
        instruction = " ".join(ctx.args[2:])
        
        async for session in get_session():
            c_result = await session.exec(select(ChannelConfig).where(ChannelConfig.channel_phone == phone))
            config = c_result.first()
            
            if not config:
                 return f"❌ Channel `{phone}` not found. Assign a persona first."
            
            config.system_prompt_override = instruction
            session.add(config)
            await session.commit()
            return f"✅ Updated instructions for `{phone}`."

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
                p_name = p_res.name if p_res else  f"Unknown ID: {c.persona_id}"
                has_override = "📝" if c.system_prompt_override else ""
                msg += f"- `{c.channel_phone}` -> **{p_name}** {has_override}\n"
            return msg
            
    return f"❌ Unknown action: {action}"
