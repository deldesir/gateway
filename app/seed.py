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
        "allowed_tools": ["fetch_dossier", "retrieval"],
    },
    {
        "slug": "konex-sales",
        "name": "Konex Sales",
        "personality": "Energetic, persuasive, enthusiastic, proactive.",
        "style": "Casual, uses emojis, speaks in Haitian Creole, focuses on upselling plans.",
        "language": "ht",
        "allowed_tools": ["start_flow", "retrieval"],
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
            "get_talkprep_help", "talkmaster_status", "select_active_talk",
            "list_publications", "list_topics", "import_talk",
            "create_revision", "develop_section",
            "evaluate_talk", "get_evaluation_scores",
            "rehearsal_cue", "export_talk_summary",
            "cost_report", "generate_anki_deck", "push_to_siyuan",
            "upload_jwpub", "retrieval",
        ],
    },
    {
        "slug": "assistant",
        "name": "Assistant",
        "personality": "Friendly, casual, human.",
        "style": "Short, natural, warm — like texting a friend. Speaks Haitian Creole and English.",
        "language": "ht,en",
        "allowed_tools": ["retrieval"],
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
