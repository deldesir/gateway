"""
Persona DB seeder — populates the Persona table on first boot.

Called during FastAPI lifespan startup. Idempotent: only inserts
personas whose slug doesn't already exist, so admin edits survive.
"""

from sqlmodel import select
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
        # Hermes toolset-level names (not individual function names).
        # 'mempalace' is always added as a baseline by the engine.
        "allowed_tools": ["rapidpro", "mempalace", "session_search", "clarify"],
    },
    {
        "slug": "konex-sales",
        "name": "Konex Sales",
        "personality": "Energetic, persuasive, enthusiastic, proactive.",
        "style": "Casual, uses emojis, speaks in Haitian Creole, focuses on upselling plans.",
        "language": "ht",
        "allowed_tools": ["rapidpro", "mocks", "mempalace", "session_search", "clarify"],
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
            "talkprep", "upload", "mempalace",
            "session_search", "clarify",
        ],
    },
    {
        "slug": "assistant",
        "name": "Assistant",
        "personality": "Friendly, casual, human.",
        "style": "Short, natural, warm — like texting a friend. Speaks Haitian Creole and English.",
        "language": "ht,en",
        "allowed_tools": ["mempalace", "session_search", "clarify"],
    },
]


async def seed_personas() -> None:
    """Insert seed personas if they don't already exist in the DB."""
    async with async_session() as session:
        inserted = 0
        for data in _SEED_DATA:
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
