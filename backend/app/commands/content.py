from .registry import CommandRegistry, CommandContext
import os
from temba_client.v2 import TembaClient

@CommandRegistry.register("learn")
async def cmd_learn(ctx: CommandContext) -> str:
    """Adds to Knowledge Base. Usage: #learn <Title> | <Content>"""
    content = " ".join(ctx.args)
    if "|" not in content: return "⚠️ Usage: `#learn Title | Content...`"
    
    title, body = content.split("|", 1)
    title = title.strip()
    body = body.strip()
    
    title, body = content.split("|", 1)
    title = title.strip()
    body = body.strip()
    
    # Placeholder for RAG integration
    return f"📝 Knowledge `{title}` added (Simulation). \nTo implement fully, link to `KnowledgeService`."

@CommandRegistry.register("global")
async def cmd_global(ctx: CommandContext) -> str:
    """Manages global vars. Usage: #global <get|set> ..."""
    if not ctx.args: return "⚠️ Usage: `#global get <key>`, `#global set <key> <value>`"
    action = ctx.args[0].lower()
    
    client = TembaClient(os.getenv("RAPIDPRO_HOST"), os.getenv("RAPIDPRO_API_TOKEN"))
    
    if action == "get":
        if len(ctx.args) < 2: return "⚠️ Usage: `#global get <key>`"
        key = ctx.args[1]
        glbl = client.get_globals(key=key).first()
        if not glbl: return f"❌ Global `{key}` not found."
        return f"🌍 **{glbl.name}**: `{glbl.value}`"
        
    elif action == "set":
        if len(ctx.args) < 3: return "⚠️ Usage: `#global set <key> <value>`"
        key, value = ctx.args[1], " ".join(ctx.args[2:])
        # Check if exists to update, else create
        glbl = client.get_globals(key=key).first()
        if glbl:
            client.update_global(glbl, value=value)
        else:
            client.create_global(name=key, value=value)
        return f"✅ Global `{key}` set to `{value}`."
        
    return f"❌ Unknown action: {action}"

@CommandRegistry.register("label")
async def cmd_label(ctx: CommandContext) -> str:
    """Manages labels. Usage: #label <add> ..."""
    if not ctx.args: return "⚠️ Usage: `#label add <name>`"
    action = ctx.args[0].lower()
    
    client = TembaClient(os.getenv("RAPIDPRO_HOST"), os.getenv("RAPIDPRO_API_TOKEN"))
    
    if action == "add":
        if len(ctx.args) < 2: return "⚠️ Usage: `#label add <name>`"
        name = " ".join(ctx.args[1:])
        client.create_label(name=name)
        return f"🏷️ Label `{name}` created."
        
    return f"❌ Unknown action: {action}"
