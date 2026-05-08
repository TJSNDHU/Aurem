"""
AUREM Weekend Warmth — Sat/Sun customer touch (Section 2)
==========================================================
Per-tenant scheduler that fires:
  • Saturday  09:00 local → warm weather/event message (SMS + Email)
  • Sunday    08:00 local → rotating quote + leads-queued teaser (SMS)

Local time is derived from each tenant's postal_code (FSA → IANA timezone),
falling back to America/Toronto. We tick HOURLY — on each tick we scan
tenants whose **current** local hour matches the spec and who haven't been
sent today.

Idempotency: each send writes a row in `weekend_warmth_log` keyed by
(tenant_id, kind, local_date) so a hot-reload or duplicate scheduler can
never double-send.

No sales pitch. No CTA. Pure rapport.
"""
from __future__ import annotations

import os
import asyncio
import logging
import random
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

try:
    from zoneinfo import ZoneInfo
except ImportError:  # py < 3.9
    from backports.zoneinfo import ZoneInfo  # type: ignore

logger = logging.getLogger(__name__)

_db = None

# Map common Canadian FSA prefixes → IANA timezone.
_FSA_TZ = {
    # Eastern (Toronto)
    "M": "America/Toronto", "L": "America/Toronto", "K": "America/Toronto",
    "N": "America/Toronto", "P": "America/Toronto",
    # Quebec
    "H": "America/Toronto", "J": "America/Toronto", "G": "America/Toronto",
    # Atlantic
    "E": "America/Moncton", "B": "America/Halifax",
    "C": "America/Halifax", "A": "America/St_Johns",
    # Prairies
    "R": "America/Winnipeg", "S": "America/Regina",
    "T": "America/Edmonton",
    # Pacific / North
    "V": "America/Vancouver", "X": "America/Yellowknife", "Y": "America/Whitehorse",
}
DEFAULT_TZ = "America/Toronto"

# 52 quotes — one per week, no repeats per calendar year. Chosen for blue-collar
# Canadian small-business owners: practical grit, no toxic hustle, no philosophy
# fluff. Mix of Canadian voices + universal ones, kept under 140 chars for SMS.
_QUOTES: List[str] = [
    "Whether you think you can or you can't, you're right.",
    "Hard work beats talent when talent doesn't work hard.",
    "The best time to plant a tree was 20 years ago. The second best time is today.",
    "Small daily improvements are the key to staggering long-term results.",
    "Don't watch the clock. Do what it does — keep going.",
    "Discipline is choosing between what you want now and what you want most.",
    "Success is the sum of small efforts repeated day in and day out.",
    "Show up. Even when you don't feel like it. Especially then.",
    "You don't have to be great to start. You have to start to be great.",
    "Action is the antidote to despair.",
    "What gets measured gets managed.",
    "The only way out is through.",
    "Pressure is a privilege.",
    "Quality is doing it right when no one is looking.",
    "If you're going through hell, keep going.",
    "Done is better than perfect.",
    "Make it. Then make it better.",
    "You miss 100% of the shots you don't take. — Wayne Gretzky",
    "The harder I work, the luckier I get.",
    "Success isn't owned. It's leased — and the rent is due every day.",
    "Comparison is the thief of joy.",
    "Worry less. Build more.",
    "Slow is smooth. Smooth is fast.",
    "The cave you fear to enter holds the treasure you seek.",
    "Be so good they can't ignore you.",
    "Persistent. Stubborn. Unstoppable.",
    "Trust the process — but check the work.",
    "Great work is built one day at a time.",
    "Output beats opinion.",
    "Habits are the compound interest of self-improvement.",
    "Aim small, miss small.",
    "Most overnight successes took a decade.",
    "Stay hungry. Stay humble.",
    "Move quietly. Build loudly.",
    "Do today what others won't, live tomorrow how others can't.",
    "Direction beats speed every time.",
    "Reps. Reps. Reps.",
    "Adversity introduces a person to themselves.",
    "Don't compete. Dominate quietly.",
    "Everyone you meet is fighting a battle you know nothing about. Be kind.",
    "If it matters, do it now.",
    "Better is the enemy of best — but done is the enemy of perfect.",
    "Excuses are the nails used to build a house of failure.",
    "The first hour sets the day.",
    "Fall down seven times. Stand up eight.",
    "Bet on yourself. The dividends compound.",
    "Show up early. Stay late. Outwork everyone.",
    "Make the lead. Take the call. Send the message.",
    "Process over panic.",
    "Plant trees you'll never sit under.",
    "Quiet weeks build loud years.",
    "The grind respects the consistent — not the talented.",
]


def set_db(database):
    global _db
    _db = database


# ─────────────────────────────────────────────────────────────────────
# Public scheduler — call once from startup
# ─────────────────────────────────────────────────────────────────────

async def weekend_warmth_scheduler() -> None:
    """Hourly tick — fire warm messages for tenants where local time matches."""
    while True:
        try:
            await _run_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"[weekend-warmth] tick failed: {e}")
        # Sleep until top of next hour + small jitter
        now = datetime.now(timezone.utc)
        secs_to_next = (60 - now.minute) * 60 - now.second
        await asyncio.sleep(max(60, secs_to_next + random.randint(0, 30)))


async def _run_once() -> Dict[str, int]:
    if _db is None:
        return {"sent_sat": 0, "sent_sun": 0, "skipped": 0}

    sent_sat = 0
    sent_sun = 0
    skipped = 0

    cursor = _db.platform_users.find(
        {"email": {"$ne": None}},
        {"_id": 0, "id": 1, "email": 1, "phone": 1, "business_id": 1,
         "business_name": 1, "company_name": 1, "full_name": 1, "first_name": 1,
         "postal_code": 1, "tz": 1},
    )
    async for user in cursor:
        try:
            tz_name = (user.get("tz") or _postal_to_tz(user.get("postal_code")) or DEFAULT_TZ)
            try:
                tz = ZoneInfo(tz_name)
            except Exception:
                tz = ZoneInfo(DEFAULT_TZ)
            now_local = datetime.now(tz)
            wd = now_local.weekday()  # Mon=0 … Sun=6
            hr = now_local.hour
            kind = None
            if wd == 5 and hr == 9:
                kind = "saturday_warmth"
            elif wd == 6 and hr == 8:
                kind = "sunday_quote"
            if not kind:
                skipped += 1
                continue
            # Idempotency
            local_date = now_local.strftime("%Y-%m-%d")
            tenant_id = user.get("business_id") or user.get("id") or user.get("email")
            log_id = _log_id(tenant_id, kind, local_date)
            existing = await _db.weekend_warmth_log.find_one({"_id": log_id}, {"_id": 1})
            if existing:
                skipped += 1
                continue
            # Build + send
            if kind == "saturday_warmth":
                ok = await _send_saturday(user, tz_name)
                if ok:
                    sent_sat += 1
            else:
                ok = await _send_sunday(user)
                if ok:
                    sent_sun += 1
            # Persist log either way to prevent retry storms
            await _db.weekend_warmth_log.update_one(
                {"_id": log_id},
                {"$set": {
                    "tenant_id": tenant_id, "kind": kind,
                    "email": user.get("email"), "phone": user.get("phone"),
                    "ts": datetime.now(timezone.utc), "sent": bool(ok),
                }},
                upsert=True,
            )
        except Exception as e:
            logger.debug(f"[weekend-warmth] user err: {e}")

    if sent_sat or sent_sun:
        logger.info(f"[weekend-warmth] sent_sat={sent_sat} sent_sun={sent_sun}")
    return {"sent_sat": sent_sat, "sent_sun": sent_sun, "skipped": skipped}


# ─────────────────────────────────────────────────────────────────────
# Saturday — weather + warm message
# ─────────────────────────────────────────────────────────────────────

async def _send_saturday(user: dict, tz_name: str) -> bool:
    name = (user.get("first_name") or (user.get("full_name") or "").split(" ")[0] or "there").strip()
    biz = user.get("business_name") or user.get("company_name") or "your business"
    postal = user.get("postal_code") or ""

    # Resolve location + weather (best-effort, never block on miss)
    weather: Dict[str, Any] = {"city": "Canada", "temp_c": None, "condition": "", "emoji": "🌤️"}
    try:
        from services.location_service import resolve_location, get_weather
        loc = await resolve_location(postal_code=postal)
        weather = await get_weather(loc.get("city"), loc.get("lat"), loc.get("lon"))
    except Exception as e:
        logger.debug(f"[weekend-warmth] weather lookup skipped: {e}")

    msg = _compose_saturday_msg(name, biz, weather)
    sms_ok = await _send_sms(user.get("phone"), msg)
    email_ok = False
    if not sms_ok:
        email_ok = await _send_email(user.get("email"), f"{biz} — happy Saturday {weather['emoji']}", msg)
    return sms_ok or email_ok


def _compose_saturday_msg(name: str, biz: str, weather: Dict[str, Any]) -> str:
    """3 sentences max, no sales, weather-aware, varies day-to-day."""
    city = weather.get("city") or "your city"
    cond = (weather.get("condition") or "").lower()
    temp = weather.get("temp_c")
    emoji = weather.get("emoji") or "🌤️"

    # Sentence 1 — weather hook
    if temp is not None:
        if cond in ("snow",):
            s1 = f"Hey {name}! Snowy Saturday in {city} — {temp}°C and the city's quiet."
        elif cond in ("rain", "drizzle", "thunderstorm"):
            s1 = f"Hey {name}! Wet morning in {city} — {temp}°C with the rain holding strong."
        elif cond in ("clear",) and temp >= 18:
            s1 = f"Hey {name}! Beautiful sunny day in {city} — {temp}°C."
        elif cond in ("clear",) and temp < 5:
            s1 = f"Hey {name}! Crisp clear morning in {city} — {temp}°C, blanket weather."
        elif cond in ("clouds",):
            s1 = f"Hey {name}! Cloudy {city} morning — {temp}°C and steady."
        else:
            s1 = f"Hey {name}! Saturday in {city} — {temp}°C {emoji}."
    else:
        s1 = f"Hey {name}! Saturday vibes in {city} {emoji}."

    # Sentence 2 — well-wishing without sales
    s2_pool = [
        f"Hope {biz} is having a great weekend.",
        f"Hope you're squeezing in a slow coffee before the kids/dogs/Saturday list kicks in.",
        f"No rush, no agenda — just wishing {biz} a smooth Saturday.",
        f"Whether {biz} is open or closed today, hope it's a calm one.",
    ]
    s2 = random.choice(s2_pool)

    # Sentence 3 — sign-off
    s3_pool = [
        "ORA out. 🙌",
        "— ORA",
        "Stay good. — ORA",
        "Catch you Monday 👋",
    ]
    s3 = random.choice(s3_pool)

    return f"{s1} {s2} {s3}"


# ─────────────────────────────────────────────────────────────────────
# Sunday — rotating quote + leads queued
# ─────────────────────────────────────────────────────────────────────

async def _send_sunday(user: dict) -> bool:
    name = (user.get("first_name") or (user.get("full_name") or "").split(" ")[0] or "there").strip()
    biz = user.get("business_name") or user.get("company_name") or "your business"
    quote = _pick_quote(user.get("id") or user.get("email") or "")
    leads = await _count_queued_leads(user.get("business_id"))
    msg = (
        f"Good morning {name} @ {biz}! ☀️\n"
        f"\u201c{quote}\u201d\n"
        f"{leads} leads queued for Monday 🔥"
    )
    return await _send_sms(user.get("phone"), msg)


def _pick_quote(seed: str) -> str:
    """Deterministic-ish quote rotation: same user gets a different one each Sunday."""
    week_key = datetime.now(timezone.utc).strftime("%Y-%U")
    h = hashlib.sha1(f"{seed}|{week_key}".encode()).hexdigest()
    return _QUOTES[int(h, 16) % len(_QUOTES)]


async def _count_queued_leads(business_id: Optional[str]) -> int:
    if not business_id or _db is None:
        return 0
    try:
        return await asyncio.wait_for(
            _db.campaign_leads.count_documents({
                "tenant_id": business_id,
                "status": {"$in": ["new", "queued", "verified"]},
            }),
            timeout=2.0,
        )
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _postal_to_tz(postal: Optional[str]) -> Optional[str]:
    if not postal:
        return None
    p = postal.strip().upper().replace(" ", "")
    if not p:
        return None
    return _FSA_TZ.get(p[0])


def _log_id(tenant_id: str, kind: str, local_date: str) -> str:
    return hashlib.sha1(f"{tenant_id}|{kind}|{local_date}".encode()).hexdigest()


async def _send_sms(phone: Optional[str], body: str) -> bool:
    if not phone:
        return False
    try:
        from services.twilio_service import send_sms  # standard helper
        res = await send_sms(phone, body)
        return bool(res and res.get("sid"))
    except Exception as e:
        logger.debug(f"[weekend-warmth] sms send failed: {e}")
        return False


async def _send_email(to: Optional[str], subject: str, body: str) -> bool:
    if not to:
        return False
    try:
        from services.resend_service import send_email
        res = await send_email(to=to, subject=subject, body_text=body)
        return bool(res and (res.get("id") or res.get("ok")))
    except Exception as e:
        logger.debug(f"[weekend-warmth] email send failed: {e}")
        return False


async def ensure_indexes() -> None:
    if _db is None:
        return
    try:
        await _db.weekend_warmth_log.create_index("ts")
        # Auto-prune entries older than 90 days
        await _db.weekend_warmth_log.create_index("ts", expireAfterSeconds=90 * 24 * 3600)
    except Exception as e:
        logger.debug(f"[weekend-warmth] index ensure skipped: {e}")
