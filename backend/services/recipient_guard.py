"""
Recipient Guard — Hard block on internal/own-domain email sends
================================================================
Stops AUREM from ever sending outbound campaign/SEO/etc emails to its own
domain (`@aurem.live`). The only exception is `ora@aurem.live` which is the
single inbox the team actually monitors and may receive system replies on.

Also covers a tight "DNC domains" set (extendable via env) so future internal
addresses (qa-bot@, qa@, no-reply@, etc.) cannot be silently auto-subscribed
to outbound blasts.

Wire-up: this module monkey-patches `resend.Emails.send` at server start so
every outbound path (12+ call sites) is covered by ONE guard, no per-call
edits required. Call `install_recipient_guard()` from server startup.
"""
from __future__ import annotations

import logging
import os
from typing import Iterable

logger = logging.getLogger(__name__)

# Hard-blocked domain. Aurem must NEVER send outbound campaign emails to
# its own domain (avoids self-spam loops like the qa-bot SEO probe).
BLOCKED_DOMAINS = {"aurem.live"}

# Single allowlisted address on the blocked domain — replies/system mails ok.
ALLOWED_ADDRESSES = {"ora@aurem.live"}


def _normalize(addr: str) -> str:
    if not addr or not isinstance(addr, str):
        return ""
    # Strip "Name <email@x>" → "email@x"
    if "<" in addr and ">" in addr:
        try:
            addr = addr.split("<", 1)[1].split(">", 1)[0]
        except Exception:
            pass
    return addr.strip().lower()


def is_blocked_recipient(addr: str) -> bool:
    """Return True if this address must NOT receive outbound mail."""
    norm = _normalize(addr)
    if not norm or "@" not in norm:
        return False
    if norm in ALLOWED_ADDRESSES:
        return False
    domain = norm.rsplit("@", 1)[-1]
    return domain in BLOCKED_DOMAINS


def filter_recipients(to: Iterable[str] | str) -> list[str]:
    """Return only non-blocked recipients from a single or list of addresses."""
    if isinstance(to, str):
        to = [to]
    out = []
    for a in to or []:
        if is_blocked_recipient(a):
            logger.warning(f"[recipient-guard] BLOCKED send to internal address: {a}")
            continue
        out.append(a)
    return out


def install_recipient_guard() -> bool:
    """
    Monkey-patch resend.Emails.send so EVERY outbound email path is filtered.
    Idempotent: safe to call multiple times.
    Returns True if patched, False if resend SDK unavailable.

    iter 325l — resend 2.27.0 exposes ``Emails`` at the top-level package
    and the ``resend.logs`` submodule is healthy. The historical
    ``resend.emails`` submodule fallback was permanently broken because
    in 2.27.0 that path is a sub-package (not a module) that does not
    re-export the ``Emails`` class. We drop the dead fallback — if
    ``import resend`` truly fails the install is corrupt and there is
    nothing to rescue.
    """
    try:
        # iter 326mm — route through the defensive engine shim. On the
        # production wheel `import resend` raises ModuleNotFoundError on
        # 'resend.logs'; the engine shim falls through to a direct
        # Emails class or HTTP fallback, so the guard CAN install.
        from services.email_engine import resend  # iter 326mm defensive
        Emails = getattr(resend, "Emails", None)
    except Exception as e:
        logger.warning(
            f"[recipient-guard] resend shim import failed: {e} — guard not installed"
        )
        return False

    if Emails is None:
        logger.warning("[recipient-guard] resend.Emails missing — guard not installed")
        return False

    original = getattr(Emails, "send", None)
    if original is None:
        logger.warning("[recipient-guard] resend.Emails.send missing — guard not installed")
        return False

    if getattr(original, "_aurem_guarded", False):
        return True  # already patched

    def guarded_send(params, *args, **kwargs):
        try:
            to = (params or {}).get("to") if isinstance(params, dict) else None
            if to is not None:
                filtered = filter_recipients(to)
                if not filtered:
                    logger.warning(
                        "[recipient-guard] ALL recipients blocked, skipping send: "
                        f"to={to}, subject={params.get('subject','')[:60]!r}"
                    )
                    return {"id": "blocked-internal-recipient",
                            "blocked": True,
                            "reason": "internal_domain_block"}
                params["to"] = filtered
        except Exception as e:
            logger.error(f"[recipient-guard] guard pre-check failed: {e}")
        return original(params, *args, **kwargs)

    guarded_send._aurem_guarded = True  # type: ignore
    Emails.send = guarded_send  # type: ignore
    logger.info(
        "[recipient-guard] resend.Emails.send patched — "
        f"blocking outbound to {BLOCKED_DOMAINS - ALLOWED_ADDRESSES} "
        f"(allow: {ALLOWED_ADDRESSES})"
    )
    return True


async def ensure_dnc_seeded(db) -> int:
    """
    Insert known internal addresses into `do_not_contact` so other code paths
    (auto_blast_engine, scout_dispatcher) that read DNC list also respect the
    block. Idempotent.
    Returns count of newly inserted docs.
    """
    if db is None:
        return 0
    seed = [
        # Common internal/system addresses on aurem.live
        "qa-bot@aurem.live",
        "qa@aurem.live",
        "qa-bot-invalid@aurem.live",
        "no-reply@aurem.live",
        "noreply@aurem.live",
        "support@aurem.live",
        "admin@aurem.live",
        "test@aurem.live",
        "hello@aurem.live",
        "team@aurem.live",
    ]
    # Allow extra entries via env (comma-separated)
    extra = os.environ.get("AUREM_INTERNAL_BLOCKED_EMAILS", "")
    if extra:
        seed.extend([e.strip().lower() for e in extra.split(",") if e.strip()])

    inserted = 0
    for email in set(e.lower() for e in seed):
        try:
            res = await db.do_not_contact.update_one(
                {"email": email},
                {"$setOnInsert": {
                    "email": email,
                    "channel": "all",
                    "reason": "internal_aurem_domain_blocked",
                    "source": "recipient_guard_seed",
                }},
                upsert=True,
            )
            if getattr(res, "upserted_id", None):
                inserted += 1
        except Exception as e:
            logger.warning(f"[recipient-guard] DNC seed failed for {email}: {e}")
    if inserted:
        logger.info(f"[recipient-guard] seeded {inserted} internal addresses into do_not_contact")
    return inserted
