"""
NotebookLM research skill — iter 282al.

Isolated from the main outreach pipeline. Only fires when the ORA skill
router selects `notebooklm_research`. Never raises — returns a
human-readable string on any failure. ALL imports of the notebooklm-py
SDK are wrapped in try/except so a missing / broken install cannot take
down the app on boot.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Module-level import guard — a missing `notebooklm-py` or broken SDK
# must never crash the app. We re-check at call time too.
try:
    from notebooklm import NotebookLMClient  # type: ignore
    _NBLM_OK = True
except Exception as _e:  # noqa: BLE001 — broad is intentional
    NotebookLMClient = None  # type: ignore
    _NBLM_OK = False
    logger.warning(f"[notebooklm] SDK unavailable at import: {_e}")


DISABLED_MSG = (
    "NotebookLM not connected. Set NOTEBOOKLM_AUTH_JSON in env to enable."
)


def _has_auth() -> bool:
    v = os.environ.get("NOTEBOOKLM_AUTH_JSON", "").strip()
    if not v:
        return False
    # Accept either a path to an auth file OR the raw JSON blob.
    if os.path.isfile(v):
        return True
    try:
        json.loads(v)
        return True
    except Exception:
        return False


async def research_lead(lead: dict, question: str) -> str:
    """Create a temporary NotebookLM notebook, add the lead's website as a
    source, ask the question, return the answer, then delete the notebook.

    Never raises — returns an error string on any failure.
    """
    if not _NBLM_OK or NotebookLMClient is None:
        return DISABLED_MSG
    if not _has_auth():
        return DISABLED_MSG
    if not question:
        return "NotebookLM skill received an empty question."

    biz = (lead or {}).get("business_name") or "Unknown"
    website = (lead or {}).get("website") or (lead or {}).get("website_url")

    nb_id: Optional[str] = None
    try:
        async with await NotebookLMClient.from_storage() as client:  # type: ignore[attr-defined]
            try:
                nb = await client.notebooks.create(f"AUREM Lead: {biz}")
                nb_id = getattr(nb, "id", None) or nb.get("id")  # type: ignore[union-attr]
            except Exception as e:
                logger.warning(f"[notebooklm] notebook create failed: {e}")
                return f"NotebookLM unavailable: {type(e).__name__}"

            if website and str(website).startswith(("http://", "https://")):
                try:
                    await client.sources.add_url(nb_id, str(website))
                except Exception as e:
                    logger.debug(f"[notebooklm] add_url failed: {e}")
                    # Non-fatal — we can still ask without sources

            try:
                result = await asyncio.wait_for(
                    client.chat.ask(nb_id, question),
                    timeout=30.0,
                )
            except Exception as e:
                logger.warning(f"[notebooklm] chat.ask failed: {e}")
                return f"NotebookLM unavailable: {type(e).__name__}"

            answer = getattr(result, "answer", None) or str(result)
            return answer.strip() if answer else "(NotebookLM returned empty answer)"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[notebooklm] session error: {e}")
        return f"NotebookLM unavailable: {type(e).__name__}"
    finally:
        # Best-effort cleanup — a new client, since the session closed.
        if nb_id and _NBLM_OK and _has_auth():
            try:
                async with await NotebookLMClient.from_storage() as cli2:  # type: ignore[attr-defined]
                    await cli2.notebooks.delete(nb_id)
            except Exception as e:
                logger.debug(f"[notebooklm] cleanup delete failed: {e}")


def research_lead_sync(lead: dict, question: str) -> str:
    """Sync wrapper for pytest / CLI use."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(
                    lambda: asyncio.run(research_lead(lead, question))
                ).result()
    except RuntimeError:
        pass
    return asyncio.run(research_lead(lead, question))


__all__ = ["research_lead", "research_lead_sync", "DISABLED_MSG"]
