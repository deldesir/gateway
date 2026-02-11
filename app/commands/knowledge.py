from .registry import CommandRegistry, CommandContext
from app.db import get_session
from app.models import Persona
from sqlmodel import select
from pathlib import Path
import asyncio
from app.rag.ingest_konex import ingest_konex

KNOWLEDGE_DIR = Path("data/knowledge")

@CommandRegistry.register("knowledge")
async def cmd_knowledge(ctx: CommandContext) -> str:
    """Manage knowledge base. Usage: #knowledge <add|read|ingest> ..."""
    if not ctx.args:
        return (
            "⚠️ **Usage**: `#knowledge <action> ...`\n"
            "- `add <persona_id> <text>`: Add fact to persona knowledge.\n"
            "- `read <persona_id>`: View current knowledge file.\n"
            "- `ingest`: Force re-index of all knowledge."
        )
        
    action = ctx.args[0].lower()
    
    if action == "add":
        if len(ctx.args) < 3:
            return "⚠️ Usage: `#knowledge add <persona_id> <content>`"
        
        target = ctx.args[1]
        content = " ".join(ctx.args[2:])
        
        # 1. Resolve Persona ID
        # We assume target is ID or Slug. 
        # Safety: Check if file exists OR if Persona exists in DB.
        # Prefer using ID as slug.
        
        target_path = KNOWLEDGE_DIR / f"{target}.md"
        
        # Check if persona exists in DB to be safe
        async for session in get_session():
             res = await session.exec(select(Persona).where(Persona.id == target))
             persona = res.first()
             if not persona:
                 # Try name lookup
                 res = await session.exec(select(Persona).where(Persona.name == target))
                 persona = res.first()
                 if persona:
                     # Use ID from found persona
                     target_path = KNOWLEDGE_DIR / f"{persona.id}.md"
                 else:
                     return f"❌ Persona `{target}` not found."
             break
        
        # 2. Append Content
        try:
            # Ensure newline prefix if file not empty
            if target_path.exists():
                current = target_path.read_text(encoding="utf-8")
                if current and not current.endswith("\n"):
                    content = "\n" + content
            
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n{content}")
                
            msg = f"✅ Added to `{target_path.name}`.\n"
            
            # 3. Trigger Ingestion (Async)
            # Run in executor to not block
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, ingest_konex)
            msg += "📥 Re-ingestion complete."
            
            return msg
        except Exception as e:
            return f"❌ Error updating knowledge: {e}"

    elif action == "read":
        if len(ctx.args) < 2:
            return "⚠️ Usage: `#knowledge read <persona_id>`"
            
        target = ctx.args[1]
        target_path = KNOWLEDGE_DIR / f"{target}.md"
        
        if not target_path.exists():
            # Try to resolve Name -> ID
            async for session in get_session():
                 res = await session.exec(select(Persona).where(Persona.name == target))
                 persona = res.first()
                 if persona:
                     target_path = KNOWLEDGE_DIR / f"{persona.id}.md"
                 break
        
        if not target_path.exists():
            return f"❌ Knowledge file not found for `{target}`."
            
        content = target_path.read_text(encoding="utf-8")
        if not content:
            return "📭 File is empty."
            
        # Truncate if too long for chat?
        if len(content) > 2000:
            return f"📄 **{target_path.name}** (Truncated):\n\n{content[:2000]}..."
            
        return f"📄 **{target_path.name}**:\n\n{content}"

    elif action == "ingest":
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, ingest_konex)
            return "✅ Knowledge re-ingested successfully."
        except Exception as e:
            return f"❌ Ingestion failed: {e}"

    return f"❌ Unknown action: {action}"
