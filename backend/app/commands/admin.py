from .registry import CommandRegistry, CommandContext
from app.db import get_session
from app.models import Admin
from sqlmodel import select
import json
import os

@CommandRegistry.register("admin")
async def cmd_admin(ctx: CommandContext) -> str:
    """Manages admin permissions.
    Usage:
    - #admin add <user_urn> <channel_urn> [permissions...] (e.g. #admin add whatsapp:123 whatsapp:456 user flow)
    - #admin remove <user_urn> <channel_urn>
    - #admin list [channel_urn]
    """
    if not ctx.args: 
        return "⚠️ Usage: `#admin add <user> <channel> [perms]`, `#admin remove <user> <channel>`, `#admin list`"
    
    action = ctx.args[0].lower()
    
    # Helper to clean/resolve URNs (Reused from CRM, maybe move to utils?)
    def clean_urn(identity):
        import re
        # Remove scheme
        clean_id = re.sub(r"^(tel|whatsapp|telegram):", "", identity)
        # Remove + and spaces
        clean_number = re.sub(r"[\+\s]", "", clean_id)
        # Default to whatsapp for admin management (as per user context)
        # But maybe we should preserve scheme if given?
        # User said "identify both numbers".
        # Let's standardize on 'whatsapp:NUMBER' for storage if no scheme provided.
        # Check if it looks like a number
        if clean_number.isdigit():
             return f"whatsapp:{clean_number}"
        return identity # Return as-is if weird

    # 1. LIST ADMINS
    if action == "list":
        # Argument 1 could be channel
        target_channel = clean_urn(ctx.args[1]) if len(ctx.args) > 1 else None
        
        async for session in get_session():
            query = select(Admin)
            if target_channel:
                query = query.where(Admin.channel_phone == target_channel)
            
            results = await session.exec(query)
            admins = results.all()
            
            if not admins:
                return f"No admins found{' for channel ' + target_channel if target_channel else ''}."
                
            msg = "🛡️ **Admin List**:\n"
            for a in admins:
                msg += f"- User: `{a.user_phone}` | Channel: `{a.channel_phone}` | Perms: `{a.permissions}`\n"
            return msg

    # 2. ADD ADMIN
    elif action == "add":
        if len(ctx.args) < 3:
            return "⚠️ Usage: `#admin add <user> <channel> [perms]`\nExample: `#admin add +5098888 +5099999 user`"
        
        user_urn = clean_urn(ctx.args[1])
        channel_urn = clean_urn(ctx.args[2])
        
        # Parse permissions
        perms_list = ctx.args[3:]
        if not perms_list:
            perms_str = "*"
        else:
            perms_str = json.dumps(perms_list)
            
        async for session in get_session():
            # Check if exists
            statement = select(Admin).where(Admin.user_phone == user_urn, Admin.channel_phone == channel_urn)
            results = await session.exec(statement)
            existing = results.first()
            
            if existing:
                existing.permissions = perms_str
                existing.created_by = ctx.user_id
                session.add(existing)
                await session.commit()
                return f"✅ Updated: User `{user_urn}` on `{channel_urn}` -> `{perms_str}`."
            else:
                new_admin = Admin(
                    user_phone=user_urn, 
                    channel_phone=channel_urn, 
                    permissions=perms_str,
                    created_by=ctx.user_id
                )
                session.add(new_admin)
                await session.commit()
                return f"✅ Added: User `{user_urn}` on `{channel_urn}` -> `{perms_str}`."

    # 3. REMOVE ADMIN
    elif action == "remove":
        if len(ctx.args) < 3:
             return "⚠️ Usage: `#admin remove <user> <channel>`"
        
        user_urn = clean_urn(ctx.args[1])
        channel_urn = clean_urn(ctx.args[2])
        
        async for session in get_session():
            statement = select(Admin).where(Admin.user_phone == user_urn, Admin.channel_phone == channel_urn)
            results = await session.exec(statement)
            existing = results.first()
            
            if existing:
                await session.delete(existing)
                await session.commit()
                return f"🗑️ Removed: `{user_urn}` from `{channel_urn}`."
            else:
                return f"❌ Not found: `{user_urn}` / `{channel_urn}`."

    return f"❌ Unknown action: {action}"
