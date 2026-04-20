from .registry import CommandRegistry, CommandContext
import os
import shutil
from pathlib import Path
from datetime import datetime

_skills_dir = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))) / "skills"


@CommandRegistry.register("skills")
async def cmd_skills(ctx: CommandContext) -> str:
    """List or manage agent-created skills (e.g., #skills, #skills delete <name>)."""
    if len(ctx.args) == 0 or ctx.args[0] == "list":
        if not _skills_dir.exists():
            return "🛡️ **Skill Audit**\nNo agent-created skills found."
            
        skills = [d for d in _skills_dir.iterdir() if d.is_dir() and d.name != ".cache"]
        if not skills:
            return "🛡️ **Skill Audit**\nNo agent-created skills found."
            
        lines = ["🛡️ **Skill Audit (Agent-Created Skills)**"]
        for s in skills:
            stat = s.stat()
            created = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"- **{s.name}** (Modified: {created})")
        lines.append("\n*To delete a suspicious skill, send `#skills delete <name>`*")
        return "\n".join(lines)
        
    elif ctx.args[0] == "delete" and len(ctx.args) > 1:
        skill_name = ctx.args[1]
        target = _skills_dir / skill_name
        
        # Security: path traversal protection using resolved absolute paths
        if not target.exists() or target.resolve().parent != _skills_dir.resolve():
            return f"❌ Skill '{skill_name}' not found."
            
        try:
            shutil.rmtree(target)
            return f"🗑️ Skill '{skill_name}' successfully deleted."
        except Exception as e:
            return f"❌ Failed to delete skill: {str(e)}"
            
    return "❌ Usage: `#skills` or `#skills delete <name>`"
