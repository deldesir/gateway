"""
Gateway tool for processing .jwpub file uploads from WhatsApp.

When a user sends a .jwpub file via WhatsApp, the LLM sees an attachment
context in the message and calls this tool with the media URL. The tool
downloads the file, extracts it into the JWLinker database, and returns
a summary of available topics.
"""

import os
import re
import logging
import asyncio
import tempfile
from typing import Optional

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def upload_jwpub(media_url: str, pub_code: Optional[str] = None) -> str:
    """Process a .jwpub file from a WhatsApp attachment URL.

    Downloads the file, decrypts it, and extracts all topics into the
    JWLinker database so they can be imported into TalkMaster.

    Args:
        media_url: The download URL for the .jwpub file (from WhatsApp attachment).
        pub_code: Optional publication code override (auto-detected from file if omitted).

    Returns:
        Summary of extracted topics, or an error message.
    """
    def _sync():
        from jwlinker.core.jwpub import JWPUBReader
        from jwlinker.core.db_manager import DBManager
        from pathlib import Path

        # 1. Download the file
        logger.info(f"Downloading .jwpub from: {media_url[:80]}...")
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.get(media_url)
                resp.raise_for_status()
        except Exception as e:
            return f"❌ Could not download file: {e}"

        # Save to temp file
        tmp = tempfile.NamedTemporaryFile(suffix=".jwpub", delete=False)
        tmp.write(resp.content)
        tmp.close()
        tmp_path = Path(tmp.name)

        try:
            # 2. Extract with JWPUBReader
            with JWPUBReader(tmp_path) as reader:
                pub_meta = reader.execute(
                    "SELECT Symbol, MepsLanguageIndex FROM Publication"
                )
                if not pub_meta:
                    return "❌ Invalid .jwpub file: no Publication table found."

                jw_symbol, jw_lang_id = pub_meta[0]
                jw_lang_id = str(jw_lang_id)
                detected_code = re.sub(r"[^a-z0-9]", "", (pub_code or jw_symbol).lower())

                # 3. Save to JWLinker DB
                db_mgr = DBManager()
                db_mgr.ensure_schema()
                conn = db_mgr.get_connection()
                cur = conn.cursor()

                cur.execute(
                    "INSERT OR IGNORE INTO Publications (code, language) VALUES (?, ?)",
                    (detected_code, jw_lang_id),
                )
                cur.execute(
                    "SELECT id FROM Publications WHERE code = ? AND language = ?",
                    (detected_code, jw_lang_id),
                )
                pub_id = cur.fetchone()[0]

                cur.execute(
                    "INSERT OR IGNORE INTO Categories (publication_id, name) VALUES (?, ?)",
                    (pub_id, "General"),
                )
                cur.execute(
                    "SELECT id FROM Categories WHERE publication_id = ? AND name = ?",
                    (pub_id, "General"),
                )
                default_cat_id = cur.fetchone()[0]

                topics_saved = 0

                def traverse(parent_id, current_cat_id):
                    nonlocal topics_saved
                    children = reader.execute("""
                        SELECT PublicationViewItemId, Title, DefaultDocumentId
                        FROM PublicationViewItem
                        WHERE ParentPublicationViewItemId = ?
                    """, (parent_id,))
                    for child_id, title, doc_id in children:
                        child_count = reader.execute(
                            "SELECT COUNT(*) FROM PublicationViewItem "
                            "WHERE ParentPublicationViewItemId = ?",
                            (child_id,),
                        )[0][0]
                        next_cat_id = current_cat_id
                        if doc_id is None:
                            if title and title.strip():
                                cur.execute(
                                    "INSERT OR IGNORE INTO Categories "
                                    "(publication_id, name) VALUES (?, ?)",
                                    (pub_id, title),
                                )
                                cur.execute(
                                    "SELECT id FROM Categories "
                                    "WHERE publication_id = ? AND name = ?",
                                    (pub_id, title),
                                )
                                next_cat_id = cur.fetchone()[0]
                            traverse(child_id, next_cat_id)
                        else:
                            if child_count > 0 and title and title.strip():
                                cur.execute(
                                    "INSERT OR IGNORE INTO Categories "
                                    "(publication_id, name) VALUES (?, ?)",
                                    (pub_id, title),
                                )
                                cur.execute(
                                    "SELECT id FROM Categories "
                                    "WHERE publication_id = ? AND name = ?",
                                    (pub_id, title),
                                )
                                next_cat_id = cur.fetchone()[0]
                            content = reader.get_document_content(doc_id) or ""
                            cur.execute("""
                                INSERT INTO Topics (category_id, name, content)
                                VALUES (?, ?, ?)
                                ON CONFLICT(category_id, name)
                                DO UPDATE SET content=excluded.content
                            """, (next_cat_id, title, content))
                            topics_saved += 1
                            if child_count > 0:
                                traverse(child_id, next_cat_id)

                roots = reader.execute(
                    "SELECT PublicationViewItemId FROM PublicationViewItem "
                    "WHERE ParentPublicationViewItemId = -1"
                )
                for root in roots:
                    traverse(root[0], default_cat_id)

                conn.commit()
                conn.close()

            return (
                f"✅ *Publication extracted!*\n"
                f"• Symbol: {jw_symbol}\n"
                f"• Code: `{detected_code}`\n"
                f"• Language ID: {jw_lang_id}\n"
                f"• Topics saved: {topics_saved}\n\n"
                f"You can now:\n"
                f"• `import talk <topic>` — import a specific topic\n"
                f"• `list topics {detected_code}` — see all available topics"
            )

        except Exception as e:
            logger.error(f"JWPUB extraction failed: {e}")
            return f"❌ Extraction failed: {e}"
        finally:
            tmp_path.unlink(missing_ok=True)

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"upload_jwpub failed: {e}")
        return f"Error processing .jwpub file: {e}"
