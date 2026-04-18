from .registry import CommandRegistry, CommandContext
import os
from pathlib import Path

_sessions_dir = Path(os.getenv(
    "HERMES_HOME", str(Path.home() / ".hermes")
)) / "sessions"


@CommandRegistry.register("reset")
async def cmd_reset(ctx: CommandContext) -> str:
    """Wipes conversation history for the current session."""
    session_file = _sessions_dir / f"session_{ctx.thread_id}.json"

    deleted = False
    if session_file.exists():
        session_file.unlink()
        deleted = True

    # Also clear legacy checkpointer if present
    if ctx.checkpointer is not None and hasattr(ctx.checkpointer, "adelete_thread"):
        try:
            await ctx.checkpointer.adelete_thread(ctx.thread_id)
        except Exception:
            pass

    if deleted:
        return "✅ Memory wiped. Conversation history has been reset."
    return "✅ No previous conversation found. Starting fresh."


@CommandRegistry.register("debug")
async def cmd_debug(ctx: CommandContext) -> str:
    """Returns system debug info."""
    return (
        f"🐛 **System Diagnostics**\n"
        f"- **User**: `{ctx.user_id}`\n"
        f"- **Thread**: `{ctx.thread_id}`\n"
        f"- **Persona**: `{ctx.persona}`\n"
        f"- **Commands Loaded**: `{len(CommandRegistry._commands)}`"
    )


@CommandRegistry.register("nuke")
async def cmd_nuke(ctx: CommandContext) -> str:
    """Deep clean: Resets memory AND blocks/archives in RapidPro."""
    # 1. Delete session file
    session_file = _sessions_dir / f"session_{ctx.thread_id}.json"
    if session_file.exists():
        session_file.unlink()

    # 2. Clear legacy checkpointer
    if ctx.checkpointer is not None and hasattr(ctx.checkpointer, "adelete_thread"):
        try:
            await ctx.checkpointer.adelete_thread(ctx.thread_id)
        except Exception:
            pass

    # 3. RapidPro cleanup (if configured)
    try:
        from temba_client.v2 import TembaClient
        rp_host = os.getenv("RAPIDPRO_HOST")
        rp_token = os.getenv("RAPIDPRO_API_TOKEN")
        if rp_host and rp_token:
            client = TembaClient(rp_host, rp_token)
            urn = ctx.user_id if ":" in ctx.user_id else f"tel:{ctx.user_id}"
            contact = client.get_contacts(urn=urn).first()
            if contact:
                client.bulk_block_contacts(contacts=[contact.uuid])
                client.bulk_archive_contact_messages(contacts=[contact.uuid])
                return "☢️ **NUKED**. Session wiped, user blocked, messages archived."
            return "⚠️ Session wiped, but user not found in RapidPro."
    except Exception as e:
        return f"⚠️ Session wiped, but RapidPro cleanup failed: {e}"

    return "⚠️ Session wiped. RapidPro not configured."

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
