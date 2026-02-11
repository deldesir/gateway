from .registry import CommandRegistry, CommandContext
import os
from temba_client.v2 import TembaClient

@CommandRegistry.register("reset")
async def cmd_reset(ctx: CommandContext) -> str:
    """Wipes memory for the current thread."""
    if hasattr(ctx.checkpointer, "adelete_thread"):
        await ctx.checkpointer.adelete_thread(ctx.thread_id)
        return "✅ Memory wiped. Conversation history has been reset for this phone number."
    return "❌ Checkpointer does not support deletion."

@CommandRegistry.register("debug")
async def cmd_debug(ctx: CommandContext) -> str:
    """Returns system debug info."""
    from .registry import CommandRegistry # Import inside to avoid circular dependency if needed, but registry is separate so it's fine.
    # Actually CommandRegistry is imported at top level.
    return (
        f"🐛 **System Diagnostics**\n"
        f"- **User**: `{ctx.user_id}`\n"
        f"- **Thread**: `{ctx.thread_id}`\n"
        f"- **Persona**: `{ctx.persona}`\n"
        f"- **Commands Loaded**: `{len(CommandRegistry._commands)}`"
    )

# @CommandRegistry.register("persona")
# async def cmd_persona(ctx: CommandContext) -> str:
#    """Handles persona switch requests."""
#    if ctx.args:
#        return f"🔄 **Persona Switch Requested**: `{ctx.args[0]}`.\n(Please update your RapidPro flow to send 'model={ctx.args[0]}' to persist this change.)"
#    return "⚠️ Usage: `#persona <id>`"

@CommandRegistry.register("nuke")
async def cmd_nuke(ctx: CommandContext) -> str:
    """Deep clean: Resets memory AND blocks/archives in RapidPro."""
    # 1. Reset Memory (Local)
    if hasattr(ctx.checkpointer, "adelete_thread"):
        await ctx.checkpointer.adelete_thread(ctx.thread_id)
        
    # 2. RapidPro Cleanup
    client = TembaClient(os.getenv("RAPIDPRO_HOST"), os.getenv("RAPIDPRO_API_TOKEN"))
    
    urn = ctx.user_id if ":" in ctx.user_id else f"tel:{ctx.user_id}"
    contact = client.get_contacts(urn=urn).first()
    
    if contact:
        # Block and Archive messages
        client.bulk_block_contacts(contacts=[contact.uuid])
        client.bulk_archive_contact_messages(contacts=[contact.uuid])
        return "☢️ **NUKED**. Memory wiped, user blocked, messages archived."
        
    return "⚠️ Memory wiped, but User not found in RapidPro."

@CommandRegistry.register("help")
async def cmd_help(ctx: CommandContext) -> str:
    """Lists available commands. Usage: #help [command_name]"""
    from .registry import CommandRegistry
    
    # 1. Detailed Help
    if ctx.args:
        cmd_name = ctx.args[0].lower().replace("#", "")
        handler = CommandRegistry._commands.get(cmd_name)
        
        if handler:
            doc = handler.__doc__ or "No description available."
            return f"📖 **Help: #{cmd_name}**\n{doc}"
        else:
            return f"❌ Command `#{cmd_name}` not found."

    # 2. List All
    commands = []
    for name, handler in CommandRegistry._commands.items():
        # Get first line of docstring
        doc_full = handler.__doc__ or "No description."
        doc_summary = doc_full.strip().split('\n')[0]
        commands.append(f"- `#{name}`: {doc_summary}")
    
    return "📚 **Available Commands**:\n" + "\n".join(sorted(commands)) + "\n\nTip: Use `#help <command>` for more details."
