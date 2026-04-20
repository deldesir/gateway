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
_SIYUAN_AUTH_CODE = os.getenv("SIYUAN_ACCESS_AUTH_CODE", "")

# Notebook ID cache: {notebook_name: notebook_id}
_notebook_map: Dict[str, str] = {}

# Persistent HTTP client with session cookie for SiYuan auth.
# SiYuan 3.6.x uses session-based auth: login via /api/system/loginAuth
# with the access auth code, then use the session cookie for all requests.
# Header-based "Authorization: Token <code>" is NOT supported.
_client: Optional[httpx.Client] = None
_auth_ok: bool = False


def _get_client() -> httpx.Client:
    """Return a persistent httpx.Client, authenticating on first use."""
    global _client, _auth_ok

    if _client is None:
        _client = httpx.Client(timeout=10)

    if not _auth_ok and _SIYUAN_AUTH_CODE:
        try:
            resp = _client.post(
                f"{_SIYUAN_URL}/api/system/loginAuth",
                json={"authCode": _SIYUAN_AUTH_CODE},
            )
            data = resp.json()
            if data.get("code") == 0:
                _auth_ok = True
                logger.info("SiYuan session auth OK")
            else:
                logger.warning(f"SiYuan login failed: {data.get('msg')}")
        except Exception as e:
            logger.error(f"SiYuan login error: {e}")

    return _client


# ── HTTP client ──────────────────────────────────────────────────────────────

def _siyuan_request(endpoint: str, payload: dict) -> dict:
    """
    Make a synchronous POST request to SiYuan's HTTP API.

    SiYuan's API is JSON-RPC-style: POST to /api/<endpoint> with a JSON body.
    Auth is via session cookie obtained from /api/system/loginAuth.
    """
    url = f"{_SIYUAN_URL}/api/{endpoint}"
    client = _get_client()

    try:
        resp = client.post(url, json=payload)
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


# ── Read operations ──────────────────────────────────────────────────────────

def siyuan_search(query: str, notebook: str = None, limit: int = 5) -> list:
    """
    Full-text search across SiYuan blocks.

    Args:
        query: Search query text
        notebook: Optional notebook name to scope search
        limit: Maximum results to return (default 5)

    Returns:
        List of result dicts with id, content preview, and path
    """
    payload = {"query": query}

    result = _siyuan_request("search/fullTextSearchBlock", payload)
    blocks = (result.get("data") or {}).get("blocks", [])

    # Filter by notebook if specified
    if notebook:
        nb_id = get_notebook_id(notebook)
        if nb_id:
            blocks = [b for b in blocks if b.get("box") == nb_id]

    # Return top N results, truncated
    results = []
    for b in blocks[:limit]:
        content = b.get("content", "")
        if len(content) > 500:
            content = content[:500] + "..."
        results.append({
            "id": b.get("id", ""),
            "content": content,
            "path": b.get("hPath", b.get("path", "")),
            "notebook": b.get("box", ""),
        })

    return results


def siyuan_read_doc(doc_id: str) -> Optional[str]:
    """
    Read a SiYuan document's markdown content by block ID.

    Uses the export API which returns clean markdown regardless of
    how the document was authored internally.

    Args:
        doc_id: Block ID of the document root

    Returns:
        Markdown content string, or None if not found
    """
    result = _siyuan_request("export/exportMdContent", {"id": doc_id})

    if result.get("code") != 0:
        logger.warning(f"SiYuan read failed: {result.get('msg')}")
        return None

    content = (result.get("data") or {}).get("content", "")

    # Truncate to prevent blowing the context window
    if len(content) > 8000:
        content = content[:8000] + "\n\n...(truncated — document exceeds 8000 chars)"

    return content
