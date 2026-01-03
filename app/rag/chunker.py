import json
from pathlib import Path
from typing import Iterator
from tqdm import tqdm
from app.logger import setup_logger

from app.rag.schema import Chunk

logger = setup_logger().bind(name="rag.chunker")


def _load_jsonl(path: Path) -> Iterator[dict]:
    """
    Reads a .jsonl file line by line and yields raw dicts.
    """
    logger.info(f"Loading JSONL file: {path}")

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON at line {line_number} in {path}: {e}")
                raise


def _normalize_record(record: dict) -> Chunk:
    """
    Converts a raw JSON dict into a Chunk object.
    """

    required_fields = [
        "id",
        "character",
        "character_slug",
        "season",
        "episode",
        "ep_code",
        "content_type",
        "text",
    ]

    for field in required_fields:
        if field not in record:
            logger.error(
                f"Missing required field '{field}' in record: {record.get('id')}"
            )
            raise ValueError(f"Missing required field: {field}")

    return Chunk(
        id=record["id"],
        text=record["text"],
        character=record["character"],
        character_slug=record["character_slug"],
        season=int(record["season"]),
        episode=int(record["episode"]),
        episode_code=record["ep_code"],
        episode_title=record.get("episode_title"),
        chunk_type=record["content_type"],
        metadata={
            "source_url": record.get("source_url"),
            "character_mentions": record.get("character_mentions", []),
        },
    )


def iter_chunks(jsonl_path: str | Path) -> Iterator[Chunk]:
    """
    Main public function.

    Streams a JSONL file and yields normalized Chunk objects.
    """
    path = Path(jsonl_path)

    if not path.exists():
        logger.error(f"JSONL file not found: {path}")
        raise FileNotFoundError(f"JSONL file not found: {path}")

    logger.info("Starting chunk iteration")

    total = 0
    failed = 0

    for record in tqdm(_load_jsonl(path), desc="Chunking records"):
        try:
            chunk = _normalize_record(record)
            total += 1
            yield chunk
        except Exception:
            failed += 1
            continue

    logger.info(f"Chunking completed | success={total} | failed={failed}")
