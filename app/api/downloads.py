"""
File download endpoint — serves generated assets (.apkg, .md, etc.)
from the /tmp directory as downloadable files.

Used by generate_anki_deck and similar tools that produce files
the user needs to access via a URL sent back through WhatsApp.
"""

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["downloads"])

DOWNLOADS_DIR = Path("/tmp")
# Only serve files with these extensions (security)
ALLOWED_EXTENSIONS = {".apkg", ".md", ".txt", ".pdf", ".csv"}
# Only serve files matching this prefix (security)
ALLOWED_PREFIX = "jwlinker_"


@router.get("/downloads/{filename}")
async def download_file(filename: str):
    """Serve a generated file for download.

    Security: only serves files from /tmp with whitelisted
    extensions and the jwlinker_ prefix.
    """
    # Sanitise: no path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Whitelist check
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=403, detail=f"File type {ext} not allowed")

    if not filename.startswith(ALLOWED_PREFIX):
        raise HTTPException(status_code=403, detail="File not available for download")

    filepath = DOWNLOADS_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/octet-stream",
    )
