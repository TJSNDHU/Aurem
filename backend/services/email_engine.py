"""
Email Engine — Unified Email Sending Layer
============================================
Primary: Tenant's own Resend key (from DB)
Fallback: Global RESEND_API_KEY from env
From: ora@aurem.live

Usage:
    from services.email_engine import EmailEngine
    engine = EmailEngine(db)
    result = await engine.send_message(tenant_id, "user@email.com", "Subject", "<h1>Hi</h1>")
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

# iter 326e — Defensive resend import.
# Production sometimes ships a slimmed resend wheel where `resend/__init__.py`
# does `from . import logs` but the `logs.py` submodule is missing — bare
# `import resend` then raises `ModuleNotFoundError: No module named
# 'resend.logs'` and the entire email engine falls through to a stub
# (every send errors with "Resend SDK not loaded" — observed in prod deploy
# logs 2026-05-21).
#
# Fix: import the SDK in two passes.
#   1) Try the full top-level import.
#   2) If that explodes, build a minimal namespace by importing JUST the
#      pieces email_engine actually uses (Emails class + api_key module
#      attribute). This bypasses any optional-submodule failure in
#      `resend.__init__`.
import importlib
import types

resend: types.ModuleType  # type: ignore
try:
    import resend  # type: ignore
except Exception as _resend_err:
    _engine_logger = logging.getLogger(__name__)
    _engine_logger.warning(
        f"[email_engine] resend top-level import failed: {_resend_err} — "
        f"trying direct Emails import"
    )
    try:
        # Reach past __init__ and pull the concrete classes directly.
        _emails_mod = importlib.import_module("resend.emails._emails")
        resend = types.ModuleType("resend")  # type: ignore
        resend.api_key = None                # type: ignore[attr-defined]
        resend.Emails  = _emails_mod.Emails  # type: ignore[attr-defined]
        _engine_logger.warning(
            "[email_engine] loaded Emails via resend.emails._emails fallback"
        )
    except Exception as _inner:
        # iter 326kk — last-resort HTTP fallback. Resend's `POST /emails`
        # endpoint is a stable JSON API; we don't need their Python SDK
        # at all. This keeps prod sending mail even when the wheel is
        # missing submodules or otherwise unloadable.
        _engine_logger.warning(
            f"[email_engine] resend SDK completely unavailable ({_inner}); "
            f"switching to direct HTTP fallback to api.resend.com/emails"
        )

        class _HttpEmails:
            @staticmethod
            def send(payload: dict) -> dict:
                import json as _json
                import urllib.request as _ur
                import urllib.error as _ue
                api_key = getattr(resend, "api_key", None) or \
                          os.environ.get("RESEND_API_KEY", "")
                if not api_key:
                    raise RuntimeError(
                        "Resend HTTP fallback active but no api_key set"
                    )
                req = _ur.Request(
                    "https://api.resend.com/emails",
                    data=_json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type":  "application/json",
                        # iter 326nn — Cloudflare in front of api.resend.com
                        # was returning 1010 (banned browser signature) on
                        # our naked urllib calls. Send a real UA so we look
                        # like a normal SDK client.
                        "User-Agent":    "aurem-resend-http-fallback/1.0 (python-urllib)",
                        "Accept":        "application/json",
                    },
                    method="POST",
                )
                try:
                    with _ur.urlopen(req, timeout=15) as resp:
                        body = resp.read().decode("utf-8", errors="replace")
                        try:
                            return _json.loads(body)
                        except Exception:
                            return {"raw": body}
                except _ue.HTTPError as e:
                    body = e.read().decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"Resend HTTP fallback {e.code}: {body[:300]}"
                    ) from e
                except Exception as e:
                    raise RuntimeError(
                        f"Resend HTTP fallback error: {e}"
                    ) from e

        resend = types.ModuleType("resend")          # type: ignore[assignment]
        resend.api_key = None                        # type: ignore[attr-defined]
        resend.Emails  = _HttpEmails                 # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

DEFAULT_FROM = os.environ.get("RESEND_FROM_EMAIL", "ORA <onboarding@resend.dev>")


class EmailEngine:
    def __init__(self, db):
        self.db = db

    async def _get_api_key(self, tenant_id: str) -> str:
        """Get Resend API key — tenant-specific first, then global fallback."""
        try:
            doc = await self.db.user_integrations.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0, "email_config": 1}
            )
            if doc:
                ec = doc.get("email_config", {})
                tenant_key = ec.get("resend_api_key", "")
                if tenant_key:
                    return tenant_key
        except Exception:
            pass
        return os.environ.get("RESEND_API_KEY", "")

    async def _get_from_address(self, tenant_id: str) -> str:
        """Get from address — tenant-specific or default."""
        try:
            doc = await self.db.user_integrations.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0, "email_config": 1}
            )
            if doc:
                ec = doc.get("email_config", {})
                from_name = ec.get("from_name", "")
                from_email = ec.get("from_email", "")
                if from_email:
                    return f"{from_name} <{from_email}>" if from_name else from_email
        except Exception:
            pass
        return DEFAULT_FROM

    async def send_message(
        self,
        tenant_id: str,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> Dict:
        """
        Send a single email via Resend.
        Uses tenant's own Resend key if set, falls back to global.
        """
        api_key = await self._get_api_key(tenant_id)
        if not api_key:
            return {"success": False, "error": "No Resend API key configured"}

        from_addr = await self._get_from_address(tenant_id)
        resend.api_key = api_key

        try:
            params = {
                "from": from_addr,
                "to": [to] if isinstance(to, str) else to,
                "subject": subject,
                "html": html_body,
            }
            if text_body:
                params["text"] = text_body

            result = resend.Emails.send(params)
            email_id = result.get("id", "") if isinstance(result, dict) else str(result)

            await self._log_email(tenant_id, to, subject, email_id, True)

            logger.info(f"[Email] Sent to {to[:20]}... via Resend (tenant: {tenant_id})")
            return {"success": True, "email_id": email_id, "engine": "resend"}

        except Exception as e:
            logger.error(f"[Email] Send failed: {e}")
            await self._log_email(tenant_id, to, subject, "", False, str(e))
            return {"success": False, "error": str(e), "engine": "resend"}

    async def send_campaign_batch(
        self,
        tenant_id: str,
        leads: List[Dict],
        subject_template: str,
        html_template: str,
    ) -> Dict:
        """
        Send personalized emails to a batch of leads.
        Checks do_not_contact list first. Returns sent/failed counts.
        """
        sent = 0
        failed = 0
        skipped = 0
        results = []

        # Load DNC list
        dnc_emails = set()
        try:
            dnc_cursor = self.db.do_not_contact.find(
                {"channel": {"$in": ["email", "all"]}},
                {"_id": 0, "email": 1}
            )
            async for doc in dnc_cursor:
                if doc.get("email"):
                    dnc_emails.add(doc["email"].lower())
        except Exception:
            pass

        for lead in leads:
            email = lead.get("email", "")
            if not email:
                skipped += 1
                continue
            if email.lower() in dnc_emails:
                skipped += 1
                continue

            # Personalize
            name = lead.get("contact_name") or lead.get("first_name") or "there"
            website = lead.get("website_url", "")
            biz_name = lead.get("business_name", "")
            score = lead.get("score", 50)
            issues = lead.get("issues_count", 0)

            subject = subject_template.format(
                first_name=name, business_name=biz_name,
                score=score, issues_count=issues,
            )
            html = html_template
            html = html.replace("{{first_name}}", name)
            html = html.replace("{{business_name}}", biz_name)
            html = html.replace("{{website}}", website)
            html = html.replace("{{score}}", str(score))
            html = html.replace("{{issues_count}}", str(issues))

            result = await self.send_message(tenant_id, email, subject, html)
            if result.get("success"):
                sent += 1
                results.append({"email": email, "status": "sent", "email_id": result.get("email_id")})
            else:
                failed += 1
                results.append({"email": email, "status": "failed", "error": result.get("error")})

        return {
            "sent": sent,
            "failed": failed,
            "skipped": skipped,
            "total": len(leads),
            "results": results[:20],
        }

    async def _log_email(self, tenant_id: str, to: str, subject: str, email_id: str, success: bool, error: str = ""):
        """Log email send and update usage counter."""
        try:
            await self.db.email_logs.insert_one({
                "tenant_id": tenant_id,
                "to": to,
                "subject": subject,
                "email_id": email_id,
                "success": success,
                "error": error,
                "engine": "resend",
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
            if success:
                await self.db.user_integrations.update_one(
                    {"tenant_id": tenant_id},
                    {
                        "$inc": {"emails_sent": 1},
                        "$set": {"last_email_at": datetime.now(timezone.utc).isoformat()},
                    }
                )
        except Exception as e:
            logger.warning(f"[Email] Log failed: {e}")
