"""
Persona DB seeder — populates the Persona table on first boot.

Called during FastAPI lifespan startup. Idempotent: only inserts
personas whose slug doesn't already exist, so admin edits survive.
"""

from sqlmodel import select
import os
import json
from app.db import async_session
from app.models import Persona
from app.logger import logger

seed_logger = logger.bind(name="PersonaSeed")

# ── Seed Data ────────────────────────────────────────────────────────────────
# This mirrors the old hardcoded PersonaPromptRegistry.REGISTRY.
# Once seeded, the DB is the single source of truth — these values are only
# used if a slug doesn't exist in the DB yet.

_SEED_DATA = [
    {
        "slug": "konex-support",
        "name": "Konex Support",
        "personality": "Professional, helpful, efficient, patient.",
        "style": "Formal yet friendly, speaks in Haitian Creole, focuses on solutions.",
        "language": "ht",
        # Hermes toolset-level names.
        # Dead tools removed: session_search (no FTS), clarify (no callback)
        "allowed_tools": ["rapidpro", "mempalace", "memory"],
    },
    {
        "slug": "konex-sales",
        "name": "Konex Sales",
        "personality": "Energetic, persuasive, enthusiastic, proactive.",
        "style": "Casual, uses emojis, speaks in Haitian Creole, focuses on upselling plans.",
        "language": "ht",
        "allowed_tools": ["rapidpro", "mocks", "mempalace", "memory"],
    },
    {
        "slug": "talkprep",
        "name": "TalkPrep Coach",
        "personality": (
            "Knowledgeable, encouraging, methodical, patient JW public speaking coach. "
            "Proactively guides speakers through each preparation stage."
        ),
        "style": (
            "Professional yet warm. Uses the 53-point S-38 rubric. "
            "Speaks the user's language (Haitian Creole, French, or English). "
            "On first interaction always calls get_talkprep_help to orient the user."
        ),
        "language": "ht",
        "allowed_tools": [
            "talkprep", "upload", "mempalace", "memory",
            "file", "skills", "siyuan",
        ],
    },
    {
        "slug": "assistant",
        "name": "Assistant",
        "personality": "Friendly, casual, human.",
        "style": "Short, natural, warm — like texting a friend. Speaks Haitian Creole and English.",
        "language": "ht,en",
        "allowed_tools": [
            "mempalace", "memory", "todo", "file",
            "code_execution", "terminal", "skills", "siyuan",
        ],
    },
    {
        "slug": "general",
        "name": "IIAB Assistant",
        "personality": "Helpful, knowledgeable, patient. A general-purpose assistant for everyday questions, research, and knowledge lookup. Does not have access to system tools or admin capabilities.",
        "style": "Short, natural, warm — like texting a friend. Speaks Haitian Creole and English.",
        "language": "ht,en",
        "allowed_tools": ["mempalace", "memory", "todo"],
    },
]


async def seed_personas() -> None:
    """Insert seed personas if they don't already exist in the DB."""
    # Build list of admin URNs from env variable
    admin_phones = os.getenv("ADMIN_PHONE", "").replace(" ", "").split(",")
    admin_urns = [f"whatsapp:{p.strip()}" for p in admin_phones if p.strip()]
    admin_urns_json = json.dumps(admin_urns) if admin_urns else "[]"
    
    async with async_session() as session:
        inserted = 0
        for data in _SEED_DATA:
            # Secure privileged personas against DB drops by re-applying restrictions
            if data["slug"] in ("assistant", "talkprep"):
                data["allowed_urns"] = admin_urns_json
            elif data["slug"] in ("general", "konex-support", "konex-sales"):
                data["allowed_urns"] = "[]"
                
            # Check if slug exists
            result = await session.exec(
                select(Persona).where(Persona.slug == data["slug"])
            )
            if result.first() is None:
                persona = Persona(**data)
                session.add(persona)
                inserted += 1
                seed_logger.info(f"Seeded persona: {data['slug']}")

        if inserted:
            await session.commit()
            seed_logger.info(f"Persona seeding complete: {inserted} new persona(s)")
        else:
            seed_logger.info("Persona seeding: all personas already exist")
