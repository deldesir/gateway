from .registry import CommandRegistry, CommandContext


@CommandRegistry.register("status")
async def cmd_status(ctx: CommandContext) -> str:
    """Show TalkPrep status: imported talks and revisions. Usage: #status"""
    from app.graph.tools.talkprep import talkmaster_status

    try:
        result = await talkmaster_status.ainvoke({})
        return result
    except Exception as e:
        return f"❌ Could not retrieve status: {e}"
