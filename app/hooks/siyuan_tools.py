"""
SiYuan wiki tools — read/write to SiYuan Note for persistent knowledge.

SiYuan is a local-first note-taking server running alongside IIAB.
These tools allow Hermes to:
  1. Look up existing wiki pages (notebook/page resolution)
  2. Create or update pages (upsert semantics)
  3. Append content blocks to existing pages

Authentication uses SiYuan's accessAuthCode feature (token-based).
All requests go to the local SiYuan instance via HTTP API.
"""

import logging
import os
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

_SIYUAN_URL = os.getenv("SIYUAN_API_URL", "http://localhost:6806")
_SIYUAN_TOKEN = os.getenv("SIYUAN_ACCESS_AUTH_CODE", "")

# Notebook ID cache: {notebook_name: notebook_id}
_notebook_map: Dict[str, str] = {}


# ── HTTP client ──────────────────────────────────────────────────────────────

def _siyuan_request(endpoint: str, payload: dict) -> dict:
    """
    Make a synchronous POST request to SiYuan's HTTP API.

    SiYuan's API is JSON-RPC-style: POST to /api/<endpoint> with a JSON body.
    Auth is via the Authorization header with the access auth code.
    """
    url = f"{_SIYUAN_URL}/api/{endpoint}"
    headers = {"Content-Type": "application/json"}

    if _SIYUAN_TOKEN:
        headers["Authorization"] = f"Token {_SIYUAN_TOKEN}"

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            logger.warning(f"SiYuan API error: {data.get('msg')} (endpoint={endpoint})")
        return data
    except httpx.HTTPError as e:
        logger.error(f"SiYuan request failed: {endpoint} → {e}")
        return {"code": -1, "msg": str(e), "data": None}


# ── Notebook resolution ─────────────────────────────────────────────────────

def _init_notebook_map() -> None:
    """
    Populate the notebook name→ID cache from SiYuan.

    Called once during app lifespan startup. If SiYuan is unreachable,
    the cache stays empty and wiki operations gracefully no-op.
    """
    global _notebook_map

    if not _SIYUAN_URL:
        logger.info("SiYuan disabled (no SIYUAN_API_URL)")
        return

    result = _siyuan_request("notebook/lsNotebooks", {})
    notebooks = (result.get("data") or {}).get("notebooks", [])

    _notebook_map = {nb["name"]: nb["id"] for nb in notebooks if not nb.get("closed")}
    logger.info(f"SiYuan: {len(_notebook_map)} notebooks cached: {list(_notebook_map.keys())}")


def get_notebook_id(name: str) -> Optional[str]:
    """
    Get notebook ID by name, with lazy init.

    Returns None if the notebook doesn't exist or SiYuan is unreachable.
    """
    if not _notebook_map:
        _init_notebook_map()
    return _notebook_map.get(name)


# ── Page operations ──────────────────────────────────────────────────────────

def siyuan_upsert_page(
    notebook: str,
    path: str,
    markdown: str,
) -> Optional[str]:
    """
    Create or update a SiYuan page.

    Args:
        notebook: Notebook name (resolved to ID internally)
        path: Page path within the notebook (e.g. "/Daily/2024-01-15")
        markdown: Markdown content for the page

    Returns:
        Page block ID if successful, None otherwise
    """
    nb_id = get_notebook_id(notebook)
    if not nb_id:
        logger.warning(f"Notebook '{notebook}' not found — skipping upsert")
        return None

    # Check if page exists
    result = _siyuan_request("filetree/getHPathByPath", {
        "notebook": nb_id,
        "path": path + ".sy",
    })

    if result.get("code") == 0 and result.get("data"):
        # Page exists — update content
        # First, get the page's block ID
        search_result = _siyuan_request("filetree/getIDsByHPath", {
            "notebook": nb_id,
            "path": path,
        })
        block_ids = search_result.get("data", [])
        if block_ids:
            block_id = block_ids[0]
            _siyuan_request("block/updateBlock", {
                "id": block_id,
                "dataType": "markdown",
                "data": markdown,
            })
            logger.debug(f"SiYuan: updated page {notebook}{path}")
            return block_id

    # Page doesn't exist — create it
    result = _siyuan_request("filetree/createDocWithMd", {
        "notebook": nb_id,
        "path": path,
        "markdown": markdown,
    })

    page_id = result.get("data")
    if page_id:
        logger.debug(f"SiYuan: created page {notebook}{path} → {page_id}")
    return page_id


def siyuan_append_block(
    notebook: str,
    path: str,
    markdown: str,
) -> Optional[str]:
    """
    Append a markdown block to an existing SiYuan page.

    If the page doesn't exist, creates it first.

    Args:
        notebook: Notebook name
        path: Page path within the notebook
        markdown: Markdown content to append

    Returns:
        Block ID of the appended content, or None on failure
    """
    nb_id = get_notebook_id(notebook)
    if not nb_id:
        logger.warning(f"Notebook '{notebook}' not found — skipping append")
        return None

    # Find the page's root block ID
    search_result = _siyuan_request("filetree/getIDsByHPath", {
        "notebook": nb_id,
        "path": path,
    })
    block_ids = search_result.get("data", [])

    if not block_ids:
        # Page doesn't exist — create it with the content
        return siyuan_upsert_page(notebook, path, markdown)

    # Append to existing page
    parent_id = block_ids[0]
    result = _siyuan_request("block/appendBlock", {
        "parentID": parent_id,
        "dataType": "markdown",
        "data": markdown,
    })

    block_data = result.get("data")
    if block_data and isinstance(block_data, list) and block_data:
        block_id = block_data[0].get("doOperations", [{}])[0].get("id")
        logger.debug(f"SiYuan: appended block to {notebook}{path} → {block_id}")
        return block_id

    return None
