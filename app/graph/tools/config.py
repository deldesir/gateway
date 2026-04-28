"""Configuration management tools (ADR-011 migration).

Layer 2 macros for persona, channel, admin, global, and label management.
Follows organized.py / talkprep.py pattern.

All macros are ADMIN-gated via ADMIN_MACROS in macro_bridge.

NOTE: These functions run inside asyncio.to_thread() (sync context).
We use a dedicated sync SQLAlchemy engine since the main app only has
async sessions.
"""

import json
import logging
import os
import re
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlmodel import Session

logger = logging.getLogger(__name__)

# Build sync DB URL from the async one (swap aiosqlite → sqlite, asyncpg → psycopg2)
_ASYNC_URL = os.getenv("POSTGRES_URI", "sqlite+aiosqlite:///./checkpoints.sqlite")
_SYNC_URL = (
    _ASYNC_URL
    .replace("sqlite+aiosqlite", "sqlite")
    .replace("postgresql+asyncpg", "postgresql")
)
_sync_engine = create_engine(
    _SYNC_URL,
    # SQLite: enable WAL mode for concurrent reads; timeout for write contention
    connect_args={"timeout": 10} if "sqlite" in _SYNC_URL else {},
    pool_pre_ping=True,
)

# Enable WAL mode on first connection for SQLite
if "sqlite" in _SYNC_URL:
    from sqlalchemy import event
    @event.listens_for(_sync_engine, "connect")
    def _set_wal(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


@contextmanager
def _sync_session():
    """Yield a sync SQLModel session. For use in tool functions only."""
    with Session(_sync_engine) as session:
        yield session


def _clean_urn(identity: str) -> str:
    """Normalize a phone/URN to whatsapp:<digits> format."""
    clean_id = re.sub(r"^(tel|whatsapp|telegram):", "", identity)
    clean_number = re.sub(r"[\+\s]", "", clean_id)
    if clean_number.isdigit():
        return f"whatsapp:{clean_number}"
    return identity


# ── Persona Management ──────────────────────────────────────────────────────

def macro_persona(args: dict, **kw) -> str:
    """Persona CRUD.

    Actions:
        list: Show all personas.
        show <name>: Show details for a persona.
        create <slug> <style> | <instruction>: Create a new persona.
        delete <name>: Delete a persona (if no channel dependencies).

    Returns:
        Action result or error message.
    """
    from app.models import Persona, ChannelConfig
    from sqlmodel import select

    # Parse action
    action_args = args.get("_args", [])
    if not action_args:
        return "⚠️ Usage: `persona list`, `persona show <name>`, `persona create <slug> <style> | <instruction>`, `persona delete <name>`"

    action = action_args[0].lower()
    rest = action_args[1:]

    with _sync_session() as session:
        if action == "list":
            personas = session.exec(select(Persona)).all()
            if not personas:
                return "📭 No personas found."
            msg = "🎭 *Personas*:\n"
            for p in personas:
                tools = p.allowed_tools or []
                if isinstance(tools, str):
                    try:
                        tools = json.loads(tools)
                    except Exception:
                        tools = []
                msg += f"• *{p.name}* (`{p.slug}`): {len(tools)} tools\n"
            return msg

        elif action == "show":
            if not rest:
                return "⚠️ Usage: `persona show <name>`"
            name = " ".join(rest)
            p = (
                session.exec(select(Persona).where(Persona.slug == name)).first()
                or session.exec(select(Persona).where(Persona.name == name)).first()
                or session.exec(select(Persona).where(Persona.id == name)).first()
            )
            if not p:
                return f"❌ Persona `{name}` not found."
            tools = p.allowed_tools or []
            if isinstance(tools, str):
                try:
                    tools = json.loads(tools)
                except Exception:
                    tools = []
            tool_str = ", ".join(tools) if tools else "None"
            return (
                f"🎭 *{p.name}* (`{p.id}`)\n"
                f"*Style*: {p.style}\n"
                f"*Tools*: {tool_str}\n"
                f"*System Prompt*: {p.system_prompt}"
            )

        elif action == "create":
            remaining = " ".join(rest)
            if "|" not in remaining:
                return "⚠️ Usage: `persona create <slug> <style> | <instruction>`"
            meta, instruction = remaining.split("|", 1)
            meta_parts = meta.strip().split()
            if len(meta_parts) < 2:
                return "⚠️ Slug and style required. Example: `persona create my-bot friendly | You are helpful.`"
            slug = meta_parts[0]
            style = " ".join(meta_parts[1:])
            instruction = instruction.strip()
            existing = session.exec(select(Persona).where(Persona.name == slug)).first()
            if existing:
                return f"❌ Persona `{slug}` already exists."
            new_persona = Persona(
                slug=slug, name=slug, style=style,
                personality=instruction, system_prompt=instruction,
            )
            session.add(new_persona)
            session.commit()
            return f"✅ Persona `{slug}` created.\nStyle: {style}\nPrompt: {instruction[:50]}..."

        elif action == "delete":
            if not rest:
                return "⚠️ Usage: `persona delete <name>`"
            name = rest[0]
            p = (
                session.exec(select(Persona).where(Persona.name == name)).first()
                or session.exec(select(Persona).where(Persona.id == name)).first()
            )
            if not p:
                return f"❌ Persona `{name}` not found."
            deps = session.exec(
                select(ChannelConfig).where(ChannelConfig.persona_id == p.id)
            ).all()
            if deps:
                channels = ", ".join(c.channel_phone for c in deps)
                return f"🚫 Cannot delete: assigned to channel(s): `{channels}`. Reassign first."
            session.delete(p)
            session.commit()
            return f"🗑️ Persona `{p.name}` deleted."

    return f"❌ Unknown action: {action}"


# ── Channel Management ──────────────────────────────────────────────────────

def macro_channel(args: dict, **kw) -> str:
    """Channel-persona mapping CRUD.

    Actions:
        list: Show all channel-persona mappings.
        assign <phone> <persona_name>: Map a channel to a persona.

    Returns:
        Action result or error message.
    """
    from app.models import ChannelConfig, Persona
    from sqlmodel import select

    action_args = args.get("_args", [])
    if not action_args:
        return "⚠️ Usage: `channel list`, `channel assign <phone> <persona>`"

    action = action_args[0].lower()
    rest = action_args[1:]

    with _sync_session() as session:
        if action == "list":
            configs = session.exec(select(ChannelConfig)).all()
            if not configs:
                return "📭 No channel configurations found."
            msg = "📡 *Channel Configs*:\n"
            for c in configs:
                p = session.get(Persona, c.persona_id)
                p_name = p.name if p else f"Unknown ID: {c.persona_id}"
                has_override = "📝" if c.system_prompt_override else ""
                msg += f"• `{c.channel_phone}` → *{p_name}* {has_override}\n"
            return msg

        elif action == "assign":
            if len(rest) < 2:
                return "⚠️ Usage: `channel assign <phone> <persona_name>`"
            phone = rest[0]
            persona_name = rest[1]
            p = (
                session.exec(select(Persona).where(Persona.slug == persona_name)).first()
                or session.exec(select(Persona).where(Persona.name == persona_name)).first()
                or session.exec(select(Persona).where(Persona.id == persona_name)).first()
            )
            if not p:
                return f"❌ Persona `{persona_name}` not found."
            config = session.exec(
                select(ChannelConfig).where(ChannelConfig.channel_phone == phone)
            ).first()
            if config:
                config.persona_id = p.id
                session.add(config)
                msg = f"✅ Updated channel `{phone}` → Persona `{p.name}`."
            else:
                config = ChannelConfig(channel_phone=phone, persona_id=p.id)
                session.add(config)
                msg = f"✅ Assigned channel `{phone}` → Persona `{p.name}`."
            session.commit()
            return msg

    return f"❌ Unknown action: {action}"


# ── Admin Permission Management ─────────────────────────────────────────────

def macro_admin(args: dict, **kw) -> str:
    """Admin permission management.

    Actions:
        list [channel]: List all admins, optionally filtered by channel.
        add <user> <channel> [perms]: Add/update an admin.
        remove <user> <channel>: Remove an admin.

    Returns:
        Action result or error message.
    """
    action_args = args.get("_args", [])
    if not action_args:
        return "⚠️ Usage: `admin list`, `admin add <user> <channel> [perms]`, `admin remove <user> <channel>`"

    action = action_args[0].lower()
    rest = action_args[1:]
    user_id = args.get("user_id", "")

    RIVEBOT_URL = os.getenv("RIVEBOT_URL", "http://127.0.0.1:8087")
    import httpx

    if action == "list":
        # Query RapidPro for members of the Admins group
        api_url = os.getenv("RAPIDPRO_API_URL", "http://localhost:8080/api/v2")
        api_token = os.getenv("RAPIDPRO_API_TOKEN", "")
        if not api_token:
            return "❌ RAPIDPRO_API_TOKEN not configured."
        try:
            resp = httpx.get(
                f"{api_url}/contacts.json",
                params={"group": "Admins"},
                headers={"Authorization": f"Token {api_token}"},
                timeout=5.0,
            )
            resp.raise_for_status()
            contacts = resp.json().get("results", [])
            if not contacts:
                return "📭 No admins found in the Admins group."
            msg = "🛡️ *Admin List (RapidPro Admins group)*:\n"
            for c in contacts:
                name = c.get("name", "?")
                urns = ", ".join(c.get("urns", []))
                msg += f"• `{name}` — {urns}\n"
            return msg
        except Exception as e:
            return f"❌ Could not query admins: {e}"

    elif action == "add":
        if len(rest) < 1:
            return "⚠️ Usage: `admin add <user>`"
        target_urn = _clean_urn(rest[0])
        try:
            resp = httpx.post(
                f"{RIVEBOT_URL}/admin-assign",
                json={"urn": target_urn, "action": "add"},
                timeout=5.0
            )
            if resp.status_code == 200:
                return f"✅ {target_urn} ajoute nan gwoup Administratè."
            return f"❌ {resp.json().get('detail', resp.text[:80])}"
        except Exception as e:
            return f"❌ Could not reach RiveBot: {e}"
            
    elif action == "remove":
        if len(rest) < 1:
            return "⚠️ Usage: `admin remove <user>`"
        target_urn = _clean_urn(rest[0])
        try:
            resp = httpx.post(
                f"{RIVEBOT_URL}/admin-assign",
                json={"urn": target_urn, "action": "remove"},
                timeout=5.0
            )
            if resp.status_code == 200:
                return f"🗑️ {target_urn} retire nan gwoup Administratè."
            return f"❌ {resp.json().get('detail', resp.text[:80])}"
        except Exception as e:
            return f"❌ Could not reach RiveBot: {e}"

    return f"❌ Unknown action: `{action}`. Use: list, add, remove."


# ── RapidPro Globals ────────────────────────────────────────────────────────

def macro_global(args: dict, **kw) -> str:
    """RapidPro globals get/set.

    Actions:
        get <key>: Get a global variable value.
        set <key> <value>: Set a global variable.

    Returns:
        Variable value or confirmation.
    """
    from temba_client.v2 import TembaClient

    action_args = args.get("_args", [])
    if not action_args:
        return "⚠️ Usage: `global get <key>`, `global set <key> <value>`"

    action = action_args[0].lower()
    rest = action_args[1:]

    rp_host = os.getenv("RAPIDPRO_HOST")
    rp_token = os.getenv("RAPIDPRO_API_TOKEN")
    if not rp_host or not rp_token:
        return "❌ RapidPro not configured."

    client = TembaClient(rp_host, rp_token)

    if action == "get":
        if not rest:
            return "⚠️ Usage: `global get <key>`"
        key = rest[0]
        glbl = client.get_globals(key=key).first()
        if not glbl:
            return f"❌ Global `{key}` not found."
        return f"🌍 *{glbl.name}*: `{glbl.value}`"

    elif action == "set":
        if len(rest) < 2:
            return "⚠️ Usage: `global set <key> <value>`"
        key = rest[0]
        value = " ".join(rest[1:])
        glbl = client.get_globals(key=key).first()
        if glbl:
            client.update_global(glbl, value=value)
        else:
            client.create_global(name=key, value=value)
        return f"✅ Global `{key}` set to `{value}`."

    return f"❌ Unknown action: {action}"


# ── Label Management ────────────────────────────────────────────────────────

def macro_label(args: dict, **kw) -> str:
    """Label management.

    Actions:
        add <name>: Create a new label.

    Returns:
        Confirmation of label creation.
    """
    from temba_client.v2 import TembaClient

    action_args = args.get("_args", [])
    if not action_args:
        return "⚠️ Usage: `label add <name>`"

    action = action_args[0].lower()
    rest = action_args[1:]

    rp_host = os.getenv("RAPIDPRO_HOST")
    rp_token = os.getenv("RAPIDPRO_API_TOKEN")
    if not rp_host or not rp_token:
        return "❌ RapidPro not configured."

    client = TembaClient(rp_host, rp_token)

    if action == "add":
        if not rest:
            return "⚠️ Usage: `label add <name>`"
        name = " ".join(rest)
        client.create_label(name=name)
        return f"🏷️ Label `{name}` created."

    return f"❌ Unknown action: {action}"
