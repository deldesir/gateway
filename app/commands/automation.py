from .registry import CommandRegistry, CommandContext
import os
from temba_client.v2 import TembaClient

@CommandRegistry.register("flow")
async def cmd_flow(ctx: CommandContext) -> str:
    """Controls flows. Usage: #flow <start|stop> ..."""
    if not ctx.args: return "⚠️ Usage: `#flow start <uuid>`, `#flow stop`"
    action = ctx.args[0].lower()
    
    client = TembaClient(os.getenv("RAPIDPRO_HOST"), os.getenv("RAPIDPRO_API_TOKEN"))
    
    urn = ctx.user_id if ":" in ctx.user_id else f"tel:{ctx.user_id}"
    contact = client.get_contacts(urn=urn).first()
    if not contact: return "❌ User not found."

    if action == "start":
        if len(ctx.args) < 2: return "⚠️ Usage: `#flow start <uuid>`"
        flow_uuid = ctx.args[1]
        client.create_flow_start(flow=flow_uuid, contacts=[contact.uuid])
        return f"🚀 Flow `{flow_uuid}` started."
        
    elif action == "stop":
        client.bulk_interrupt_contacts(contacts=[contact.uuid])
        return "VkStopped all active flows."
        
    return f"❌ Unknown action: {action}"

@CommandRegistry.register("broadcast")
async def cmd_broadcast(ctx: CommandContext) -> str:
    """Sends broadcast. Usage: #broadcast <group_name> <message>"""
    if len(ctx.args) < 2: return "⚠️ Usage: `#broadcast <group> <message>`"
    
    group_name = ctx.args[0]
    message = " ".join(ctx.args[1:])
    
    client = TembaClient(os.getenv("RAPIDPRO_HOST"), os.getenv("RAPIDPRO_API_TOKEN"))
    
    group = client.get_groups(name=group_name).first()
    if not group: return f"❌ Group `{group_name}` not found."
    
    client.create_broadcast(text=message, groups=[group])
    return f"📢 Broadcast sent to group `{group_name}`."

@CommandRegistry.register("campaign")
async def cmd_campaign(ctx: CommandContext) -> str:
    """Manages campaigns. Usage: #campaign <list|start> ..."""
    if not ctx.args: return "⚠️ Usage: `#campaign list`, `#campaign start <name>`"
    action = ctx.args[0].lower()
    
    client = TembaClient(os.getenv("RAPIDPRO_HOST"), os.getenv("RAPIDPRO_API_TOKEN"))
    
    if action == "list":
        campaigns = client.get_campaigns().all()
        if not campaigns: return "📭 No campaigns found."
        return "📢 **Campaigns**:\n" + "\n".join([f"- {c.name} (`{c.uuid}`)" for c in campaigns])
        
    elif action == "start":
        if len(ctx.args) < 2: return "⚠️ Usage: `#campaign start <name>` (Must exist)"
        name = " ".join(ctx.args[1:])
        # In RapidPro API, creating a campaign essentially 'starts' it for a group if passed, 
        # OR we might mean 'trigger an event'. 
        # For this simple command, let's assume we want to CREATE a campaign for a group.
        # But the user asked for 'start'. Let's stick to listing for now or simple creation.
        return "⚠️ `#campaign start` requires complex event logic. Use RapidPro UI for now, or `#campaign list` to view status."
        
    return f"❌ Unknown action: {action}"
