"""
WhatsApp Hybrid Engine
======================
Unified WhatsApp messaging layer.
Primary: WHAPI (per-tenant token → global env)
Fallback: Tenant Meta Cloud → Ripple Meta Cloud → SMS via Twilio
(Routing rationale: WHAPI is the operator's preferred path; Meta Cloud and
SMS are last-resort safety nets.)

Usage:
    from services.whatsapp_engine import WhatsAppEngine
    engine = WhatsAppEngine(db)
    result = await engine.send_message(tenant_id, "16134000000", "Hello!")
"""

import os
import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

META_API_VERSION = "v19.0"
META_API_BASE = f"https://graph.facebook.com/{META_API_VERSION}"
WHAPI_API_BASE = os.environ.get("WHAPI_API_URL", "https://gate.whapi.cloud")


class WhatsAppEngine:
    def __init__(self, db):
        self.db = db

    async def get_tenant_config(self, tenant_id: str) -> Dict:
        """Fetch WhatsApp config for a tenant from DB."""
        doc = await self.db.user_integrations.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "whatsapp_config": 1, "tenant_id": 1}
        )
        if not doc:
            return {"mode": "not_connected", "connected": False}

        wc = doc.get("whatsapp_config", {})
        return {
            "mode": wc.get("whatsapp_mode", "not_connected"),
            "connected": wc.get("whatsapp_connected", False),
            "meta_phone_number_id": wc.get("meta_phone_number_id", ""),
            "meta_access_token": wc.get("meta_access_token", ""),
            "meta_waba_id": wc.get("meta_waba_id", ""),
            "whapi_token": wc.get("whapi_token", ""),
            "phone_number": wc.get("phone_number", ""),
            "connected_at": wc.get("whatsapp_connected_at"),
        }

    async def send_message(self, tenant_id: str, to: str, message: str, media_url: Optional[str] = None) -> Dict:
        """
        Send a WhatsApp message. Routing priority (operator preference: WHAPI first):
          1. Per-tenant WHAPI token   (db.user_integrations.whatsapp_config.whapi_token)
          2. Global WHAPI token       (env WHAPI_API_TOKEN)
          3. Tenant Meta Cloud        (db.user_integrations.whatsapp_config.meta_access_token)
          4. Ripple Meta Cloud        (env RIPPLE_WHATSAPP_ACCESS_TOKEN + PHONE_NUMBER_ID)
          5. Twilio WhatsApp          (env TWILIO_* via channel_config)
        """
        config = await self.get_tenant_config(tenant_id)

        # Clean phone number — iter 323d: strict centralized normalizer.
        # Old logic only stripped 5 chars; WHAPI's regex `^[\d-]{9,31}` rejects
        # phones containing letters ("ext"), dots, unicode, or empty strings.
        from utils.phone_format import to_whapi_format
        to_clean = to_whapi_format(to)
        if not to_clean:
            logger.warning(f"[WhatsApp] Skipping send — invalid phone: {str(to)[:20]!r}")
            return {"success": False, "skipped": True, "error": "invalid_phone", "engine": "validator"}

        # 1. Per-tenant WHAPI
        if config.get("whapi_token"):
            result = await self._send_whapi(config, to_clean, message, media_url)
            if result["success"]:
                await self._log_message(tenant_id, to_clean, message, "whapi", result)
                return result
            logger.warning(f"[WhatsApp] Tenant WHAPI failed for {tenant_id}: {result.get('error')}. Trying global WHAPI...")

        # 2. Global WHAPI (env)
        global_token = os.environ.get("WHAPI_API_TOKEN", "")
        if global_token:
            result = await self._send_whapi_global(to_clean, message, media_url)
            if result["success"]:
                await self._log_message(tenant_id, to_clean, message, "whapi_global", result)
                await self._monitor_log("whatsapp", "whapi", "whapi", "success", None)
                try:
                    from services.fallback_monitor import reset_primary_failure
                    await reset_primary_failure(self.db, service="whatsapp", primary="whapi")
                except Exception:
                    pass
                return result
            logger.warning(f"[WhatsApp] Global WHAPI failed for {tenant_id}: {result.get('error')}. Trying Meta Cloud...")

        # 3. Tenant Meta Cloud
        if config.get("meta_access_token"):
            result = await self._send_meta(config, to_clean, message, media_url)
            if result["success"]:
                await self._log_message(tenant_id, to_clean, message, "meta_cloud", result)
                return result
            logger.warning(f"[WhatsApp] Tenant Meta Cloud failed for {tenant_id}: {result.get('error')}. Trying Ripple fallback...")

        # Tier 3 fallback: Ripple Meta Cloud (adapted from Keshav's ripple-agent)
        ripple_failed_reason = None
        try:
            from services.ripple_whatsapp_fallback import send_via_ripple, ripple_whatsapp_configured
            if ripple_whatsapp_configured():
                ripple_res = send_via_ripple(to_clean, message)
                ripple_dict = {
                    "success": ripple_res.ok,
                    "provider": "ripple-meta-cloud",
                    "detail": ripple_res.detail,
                    "preview": ripple_res.preview,
                }
                if ripple_res.ok:
                    await self._log_message(tenant_id, to_clean, message, "ripple_meta_cloud", ripple_dict)
                    await self._monitor_log("whatsapp", "whapi", "ripple", "fallback",
                                            reason="whapi_failed")
                    return ripple_dict
                ripple_failed_reason = ripple_res.detail
        except Exception as e:
            logger.warning(f"[WhatsApp] Ripple fallback error: {e}")
            ripple_failed_reason = str(e)[:200]

        # Tier 4 final fallback: SMS via Twilio (silent — same message over SMS)
        logger.warning(f"[WhatsApp] Ripple exhausted for {tenant_id} → falling back to SMS")
        sms_result = await self._send_sms_fallback(to, message)
        if sms_result.get("success"):
            await self._log_message(tenant_id, to_clean, message, "sms_fallback", sms_result)
            await self._monitor_log("whatsapp", "whapi", "sms", "fallback",
                                    reason=f"ripple_failed: {ripple_failed_reason or 'unknown'}")
            await self._monitor_fail("whatsapp", "whapi", ripple_failed_reason or "all_wa_channels_down")
            return sms_result

        await self._monitor_log("whatsapp", "whapi", None, "error",
                                reason=f"all_channels_down: ripple={ripple_failed_reason}, sms={sms_result.get('error')}")
        await self._monitor_fail("whatsapp", "whapi", "all_channels_down")
        return {
            "success": False,
            "error": "WhatsApp not configured for this tenant (all 4 tiers exhausted: tenant, WHAPI, Ripple, SMS)",
            "mode": config.get("mode", "not_connected"),
        }

    async def _send_sms_fallback(self, to: str, message: str) -> Dict:
        """Final-tier: send as SMS via Twilio when all WhatsApp channels fail."""
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        from_num = os.environ.get("TWILIO_PHONE_NUMBER", "") or os.environ.get("TWILIO_FROM_NUMBER", "")
        if not (sid and token and from_num):
            return {"success": False, "provider": "sms", "error": "twilio_not_configured"}
        try:
            import httpx
            # iter 323d — Twilio requires E.164 format (+1XXXXXXXXXX)
            from utils.phone_format import to_e164
            to_e164_val = to_e164(to)
            if not to_e164_val:
                return {"success": False, "provider": "sms", "error": "invalid_phone_for_twilio"}
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                    auth=(sid, token),
                    data={"From": from_num, "To": to_e164_val, "Body": message[:1600]},
                )
            ok = resp.status_code in (200, 201)
            data = {}
            try:
                data = resp.json()
            except Exception:
                pass
            return {
                "success": ok,
                "provider": "sms",
                "sid": data.get("sid") if ok else None,
                "error": None if ok else f"twilio_status_{resp.status_code}",
            }
        except Exception as e:
            return {"success": False, "provider": "sms", "error": str(e)[:200]}

    async def _monitor_log(self, service, primary, used, result, reason=None):
        """Log a fallback event. Silent on failure."""
        try:
            from services.fallback_monitor import log_fallback
            await log_fallback(self.db, service=service, primary=primary,
                               used=used, result=result, reason=reason)
        except Exception:
            pass

    async def _monitor_fail(self, service, primary, reason):
        """Record a primary-service failure. Silent on failure."""
        try:
            from services.fallback_monitor import record_primary_failure
            await record_primary_failure(self.db, service=service, primary=primary, reason=reason)
        except Exception:
            pass

    async def _send_meta(self, config: Dict, to: str, message: str, media_url: Optional[str] = None) -> Dict:
        """Send via Meta Cloud API."""
        phone_id = config["meta_phone_number_id"]
        token = config["meta_access_token"]

        url = f"{META_API_BASE}/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        if media_url:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "image",
                "image": {"link": media_url, "caption": message},
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": message},
            }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, headers=headers, json=payload)
                data = resp.json()
                if resp.status_code in (200, 201):
                    msg_id = data.get("messages", [{}])[0].get("id", "")
                    return {"success": True, "message_id": msg_id, "engine": "meta_cloud"}
                else:
                    error_msg = data.get("error", {}).get("message", resp.text[:200])
                    return {"success": False, "error": error_msg, "engine": "meta_cloud", "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e), "engine": "meta_cloud"}

    async def _send_whapi(self, config: Dict, to: str, message: str, media_url: Optional[str] = None) -> Dict:
        """Send via tenant's WHAPI token."""
        token = config.get("whapi_token", "")
        if not token:
            return {"success": False, "error": "No WHAPI token configured for tenant", "engine": "whapi"}
        return await self._whapi_send(token, to, message, media_url)

    async def _send_whapi_global(self, to: str, message: str, media_url: Optional[str] = None) -> Dict:
        """Send via global WHAPI token from environment."""
        token = os.environ.get("WHAPI_API_TOKEN", "")
        if not token:
            return {"success": False, "error": "WHAPI_API_TOKEN not set", "engine": "whapi_global"}
        return await self._whapi_send(token, to, message, media_url)

    async def _whapi_send(self, token: str, to: str, message: str, media_url: Optional[str] = None) -> Dict:
        """Low-level WHAPI send — hardened response parsing (iter 322g).

        WHAPI sometimes returns:
          - 200 + JSON body with `{"sent": true, "message": {"id": "..."}}`
          - 200 + JSON body without `sent` (rare, message types)
          - 200 + empty body (auth proxy edge cases)
          - 4xx/5xx + plain-text or HTML error body (non-JSON)

        We treat the request as successful only when EITHER:
          a) HTTP status is 2xx AND body parses as JSON with `sent != False`, OR
          b) HTTP status is 2xx AND `data.get("message", {}).get("id")` exists.
        Anything else returns a structured failure with the raw body excerpt.
        """
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                if media_url:
                    resp = await client.post(
                        f"{WHAPI_API_BASE}/messages/image",
                        headers=headers,
                        json={"to": to, "media": {"url": media_url}, "caption": message},
                    )
                else:
                    resp = await client.post(
                        f"{WHAPI_API_BASE}/messages/text",
                        headers=headers,
                        json={"to": to, "body": message},
                    )

            # Tolerant body parse — never let a non-JSON 5xx crash the engine.
            data: Dict = {}
            raw_excerpt = ""
            try:
                data = resp.json() or {}
            except Exception:
                raw_excerpt = (resp.text or "")[:200]

            status_ok = resp.status_code in (200, 201)
            sent_field = data.get("sent")
            msg_id = (data.get("message") or {}).get("id") or data.get("id") or ""

            # Treat explicit `sent: False` as failure even on a 2xx response.
            if status_ok and sent_field is not False and (sent_field is True or msg_id or not data):
                return {
                    "success": True,
                    "message_id": msg_id,
                    "engine": "whapi",
                    "status_code": resp.status_code,
                }

            err = (
                (data.get("error") if isinstance(data.get("error"), str) else None)
                or (data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else None)
                or data.get("message")
                or raw_excerpt
                or f"http_{resp.status_code}"
            )
            return {
                "success": False,
                "error": str(err)[:300],
                "engine": "whapi",
                "status_code": resp.status_code,
            }
        except Exception as e:
            return {"success": False, "error": str(e)[:300], "engine": "whapi"}

    async def _log_message(self, tenant_id: str, to: str, message: str, engine: str, result: Dict):
        """Log sent message and update usage counter."""
        try:
            await self.db.whatsapp_message_log.insert_one({
                "tenant_id": tenant_id,
                "to": to,
                "message": message[:500],
                "engine": engine,
                "message_id": result.get("message_id", ""),
                "success": result.get("success", False),
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
            # Increment usage counter
            await self.db.user_integrations.update_one(
                {"tenant_id": tenant_id},
                {
                    "$inc": {"whatsapp_sent": 1},
                    "$set": {"last_whatsapp_at": datetime.now(timezone.utc).isoformat()},
                }
            )
        except Exception as e:
            logger.warning(f"[WhatsApp] Log failed: {e}")

    async def verify_meta_credentials(self, phone_number_id: str, waba_id: str, access_token: str) -> Dict:
        """Validate Meta Cloud API credentials by calling the test endpoint."""
        url = f"{META_API_BASE}/{phone_number_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)
                data = resp.json()
                if resp.status_code == 200:
                    display_name = data.get("verified_name", data.get("display_phone_number", ""))
                    return {"valid": True, "phone_display_name": display_name, "data": data}
                else:
                    error = data.get("error", {}).get("message", "Invalid credentials")
                    return {"valid": False, "error": error, "status_code": resp.status_code}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    async def verify_whapi_token(self, token: str) -> Dict:
        """Validate WHAPI token by calling settings endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{WHAPI_API_BASE}/settings",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"valid": True, "phone": data.get("phone", ""), "name": data.get("name", "")}
                else:
                    return {"valid": False, "error": f"HTTP {resp.status_code}", "status_code": resp.status_code}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    async def get_status(self, tenant_id: str) -> Dict:
        """Full WhatsApp status for a tenant.

        Preference order for "connected" determination:
          1. Per-tenant Meta Cloud config in db.user_integrations (if present)
          2. Per-tenant WHAPI config in db.user_integrations (if present)
          3. System-wide Twilio WhatsApp credentials from env (channel_config)
          4. System-wide Meta WhatsApp credentials from env (channel_config)
        """
        config = await self.get_tenant_config(tenant_id)

        # Get message stats
        msg_count = 0
        last_sent = None
        try:
            msg_count = await self.db.whatsapp_message_log.count_documents({"tenant_id": tenant_id})
            last_msg = await self.db.whatsapp_message_log.find_one(
                {"tenant_id": tenant_id}, {"_id": 0, "sent_at": 1},
                sort=[("sent_at", -1)]
            )
            if last_msg:
                last_sent = last_msg.get("sent_at")
        except Exception:
            pass

        # If tenant has no explicit config, fall back to system-wide env creds.
        # Priority: global WHAPI → Twilio → Meta (matches send_message routing).
        mode = config["mode"]
        connected = config["connected"]
        phone_number = config.get("phone_number", "")
        if not connected:
            try:
                whapi_global = bool(os.environ.get("WHAPI_API_TOKEN", "").strip())
                if whapi_global:
                    mode = "whapi"
                    connected = True
                    phone_number = phone_number or "(WHAPI global)"
                else:
                    from services.channel_config import twilio_status, meta_whatsapp_status
                    t = twilio_status()
                    m = meta_whatsapp_status()
                    if t["whatsapp_configured"]:
                        mode = "twilio"
                        connected = True
                        phone_number = t["whatsapp_from"] or ""
                    elif m["configured"]:
                        mode = "meta_cloud"
                        connected = True
                        phone_number = m["phone_id"] or ""
            except Exception:
                pass

        return {
            "mode": mode,
            "connected": connected,
            "phone_number": phone_number,
            "connected_at": config.get("connected_at"),
            "last_message_sent": last_sent,
            "messages_total": msg_count,
            "engine_details": {
                "meta_configured": bool(config.get("meta_access_token")),
                "whapi_configured": bool(config.get("whapi_token")) or bool(os.environ.get("WHAPI_API_TOKEN")),
                "twilio_configured": bool(
                    os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN")
                ),
            },
        }
