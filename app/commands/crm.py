from .registry import CommandRegistry, CommandContext
import os
from temba_client.v2 import TembaClient

@CommandRegistry.register("profile")
async def cmd_profile(ctx: CommandContext) -> str:
    """Fetches user profile from RapidPro."""
    host = os.getenv("RAPIDPRO_HOST", "http://localhost:8000")
    token = os.getenv("RAPIDPRO_API_TOKEN")
    
    if not token:
        return "❌ Configuration Error: RAPIDPRO_API_TOKEN not set."
        
    client = TembaClient(host, token)
    
    urn = ctx.user_id
    if ":" not in urn:
        urn = f"tel:{urn}" 
        
    contact = client.get_contacts(urn=urn).first()
    
    if not contact:
        return f"❌ Contact not found for URN: `{urn}`"
        
    return (
        f"👤 **RapidPro Profile**\n"
        f"- **Name**: {contact.name}\n"
        f"- **UUID**: `{contact.uuid}`\n"
        f"- **Language**: {contact.language}\n"
        f"- **Groups**: {', '.join([g.name for g in contact.groups])}"
    )

@CommandRegistry.register("user")
async def cmd_user(ctx: CommandContext) -> str:
    """Manages user contact info. Usage: #user <info|update|block> ..."""
    if not ctx.args: return "⚠️ Usage: `#user info`, `#user update <field> <value>`, `#user block`"
    
    action = ctx.args[0].lower()
    
    client = TembaClient(os.getenv("RAPIDPRO_HOST"), os.getenv("RAPIDPRO_API_TOKEN"))
    
    # Determine Target URN
    # Default to current user (self)
    target_identity = ctx.user_id
    
    # Check if a target arg is provided for 'info' or 'block'
    # Usage: #user info [target_urn]
    if action in ["info", "block"] and len(ctx.args) > 1:
        target_identity = ctx.args[1]
        
    # Helper to clean number and try multiple schemes
    def resolve_contact(identity):
        # 1. Strip scheme and non-digit chars (except we want to keep the number)
        # Actually, RapidPro usually wants just the number for URNs like whatsapp:509...
        import re
        
        # Remove scheme if present
        clean_id = re.sub(r"^(tel|whatsapp|telegram):", "", identity)
        
        # Remove + and spaces
        clean_number = re.sub(r"[\+\s]", "", clean_id)
        
        # Try schemes in order of likelihood for this deployment
        schemes = ["whatsapp", "tel"]
        
        for scheme in schemes:
            urn = f"{scheme}:{clean_number}"
            contact = client.get_contacts(urn=urn).first()
            if contact:
                return contact
        return None

    contact = resolve_contact(target_identity)
    if not contact: 
        return f"❌ User not found: `{target_identity}` (Tried whatsapp/tel without +)"

    if action == "info":
        return f"👤 **{contact.name}**\nUUID: `{contact.uuid}`\nLang: {contact.language}\nGroups: {', '.join([g.name for g in contact.groups])}"
    
    elif action == "update":
        if len(ctx.args) < 3: return "⚠️ Usage: `#user update <field> <value>`"
        field, value = ctx.args[1], " ".join(ctx.args[2:])
        client.update_contact(contact.uuid, fields={field: value})
        return f"✅ Updated `{field}` to `{value}`."
        
    elif action == "block":
        client.bulk_block_contacts(contacts=[contact.uuid])
        return "🚫 User blocked."
        
    return f"❌ Unknown action: {action}"

@CommandRegistry.register("group")
async def cmd_group(ctx: CommandContext) -> str:
    """Manages groups. Usage: #group <list|create|add|kick> ..."""
    if not ctx.args: return "⚠️ Usage: `#group list`, `#group create <name>`"
    action = ctx.args[0].lower()
    
    client = TembaClient(os.getenv("RAPIDPRO_HOST"), os.getenv("RAPIDPRO_API_TOKEN"))
    
    if action == "list":
        groups = client.get_groups().all()
        return "👥 **Groups**:\n" + "\n".join([f"- {g.name} ({g.count} users)" for g in groups])
        
    elif action == "create":
        if len(ctx.args) < 2: return "⚠️ Usage: `#group create <name>`"
        name = " ".join(ctx.args[1:])
        group = client.create_group(name=name)
        return f"✅ Group `{group.name}` created."
        
    elif action == "add":
        if len(ctx.args) < 2: return "⚠️ Usage: `#group add <name>` (Adds current user)"
        name = " ".join(ctx.args[1:])
        group = client.get_groups(name=name).first()
        if not group: return f"❌ Group `{name}` not found."
        
        urn = ctx.user_id if ":" in ctx.user_id else f"tel:{ctx.user_id}"
        contact = client.get_contacts(urn=urn).first()
        if not contact: return "❌ User not found."
        
        client.bulk_add_contacts(contacts=[contact.uuid], group=group)
        return f"✅ Added to group `{name}`."

    return f"❌ Unknown action: {action}"
