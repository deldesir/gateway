from .registry import CommandRegistry, CommandContext


@CommandRegistry.register("cost")
async def cmd_cost(ctx: CommandContext) -> str:
    """Show LLM token usage and estimated cost for the current session. Usage: #cost"""
    from app.graph.tools.talkprep import cost_report

    try:
        result = await cost_report.ainvoke({})
        return result
    except Exception as e:
        return f"❌ Could not retrieve cost report: {e}"
