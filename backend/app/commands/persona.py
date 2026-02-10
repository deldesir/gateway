from .registry import CommandRegistry, CommandContext
from app.db import get_session
from app.models import Persona
from sqlmodel import select
import uuid

@CommandRegistry.register("persona")
async def cmd_persona(ctx: CommandContext) -> str:
    """Manages personas. Usage: #persona <create|list|delete|show> ..."""
    if not ctx.args: 
        return "⚠️ Usage: `#persona create <name> <style> | <instruction>`, `#persona list`, `#persona delete <name>`"
    
    action = ctx.args[0].lower()
    
    # helper for DB ops
    async def get_persona_by_name(session, name):
        result = await session.exec(select(Persona).where(Persona.name == name))
        return result.first()

    if action == "create":
        # #persona create <name> <style> | <instruction>
        # Example: #persona create support-haiti formal | You are a helpful assistant.
        
        remaining = " ".join(ctx.args[1:])
        if "|" not in remaining:
             return "⚠️ Usage: `#persona create <name> <style> | <instruction>`"
        
        meta, instruction = remaining.split("|", 1)
        meta_parts = meta.strip().split()
        if len(meta_parts) < 2:
            return "⚠️ Name and Style required. Example: `#persona create my-bot friendly | ...`"
            
        name = meta_parts[0]
        style = " ".join(meta_parts[1:])
        instruction = instruction.strip()
        
        async for session in get_session():
            existing = await get_persona_by_name(session, name)
            if existing:
                return f"❌ Persona `{name}` already exists. Use another name or delete it first."
                
            new_persona = Persona(
                name=name,
                style=style,
                personality=instruction,
                system_prompt=instruction # Using personality as system prompt for now
            )
            session.add(new_persona)
            await session.commit()
            return f"✅ Persona `{name}` created.\nStyle: {style}\nPrompt: {instruction[:50]}..."

    elif action == "list":
        async for session in get_session():
            result = await session.exec(select(Persona))
            personas = result.all()
            if not personas:
                return "📭 No personas found."
            
            msg = "🎭 **Personas**:\n"
            for p in personas:
                msg += f"- `{p.name}` ({p.style})\n"
            return msg

    elif action == "delete":
        if len(ctx.args) < 2: return "⚠️ Usage: `#persona delete <name>`"
        name = ctx.args[1]
        
        async for session in get_session():
            params = await get_persona_by_name(session, name)
            if not params:
                return f"❌ Persona `{name}` not found."
            
            await session.delete(params)
            await session.commit()
            return f"🗑️ Persona `{name}` deleted."

    elif action == "show":
        if len(ctx.args) < 2: return "⚠️ Usage: `#persona show <name>`"
        name = ctx.args[1]
        
        async for session in get_session():
            p = await get_persona_by_name(session, name)
            if not p: return f"❌ Persona `{name}` not found."
            
            return (
                f"🎭 **{p.name}**\n"
                f"**Style**: {p.style}\n"
                f"**System Prompt**: {p.system_prompt}\n"
                f"**ID**: `{p.id}`"
            )

    return f"❌ Unknown action: {action}"
