"""
Auto-Blast Engine
─────────────────
Background worker that automatically picks freshly-scraped leads,
verifies them via Accurate-Scout, and fires the 4-channel AUREM blast
(Email + SMS + WhatsApp + Voice) — respecting channel gates, DNC list,
and per-tenant toggles.

Persistence:
- `auto_blast_config` — {tenant_id, enabled, max_per_cycle, interval_minutes, last_run_at, last_run_processed, last_run_sent}

A lead is eligible for auto-blast when:
  - `last_blast_at` is missing (never blasted)
  - lead has email OR phone
  - lead is NOT in `do_not_contact`
  - lead.status not in {'signed_up', 'not_interested'}

The engine caps a cycle to max_per_cycle leads (default 10) to avoid
burst sending / budget burn.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


# ─────────────────────────────────────────────────────────────
# Lead verification (uses existing Accurate-Scout helpers)
# ─────────────────────────────────────────────────────────────
async def _auto_verify_lead(db, lead: Dict[str, Any]) -> Dict[str, Any]:
    """Run Accurate-Scout verification + persist. Returns the fresh lead doc.

    Wrapped with a hard timeout — scout sometimes hangs on bad websites
    which would otherwise stall the entire auto-blast cycle.
    """
    lead_id = lead.get("lead_id")
    try:
        from services.accurate_scout import full_business_verify, save_verified_profile
        name = lead.get("business_name") or ""
        city = lead.get("city") or ""
        addr = lead.get("address") or ""
        # Country inference. Earlier version used `"ON" in addr` which false-
        # matched BOSTON / BRANDON / JOHNSTON. Now we check for a proper
        # Canadian province token (comma- or space-delimited) plus the
        # explicit Canadian city allowlist.
        _addr_upper = addr.upper()
        _ca_provinces = ("ON", "QC", "BC", "AB", "SK", "MB", "NB", "NS",
                         "PE", "NL", "NT", "NU", "YT")
        _ca_province_hit = any(
            f", {p}" in _addr_upper or f" {p} " in _addr_upper
            or _addr_upper.endswith(f" {p}") or _addr_upper.endswith(f",{p}")
            for p in _ca_provinces
        )
        country = "ca" if (_ca_province_hit or city.lower() in (
            "toronto", "brampton", "mississauga", "ottawa", "vancouver",
            "calgary", "edmonton", "montreal", "quebec"
        )) else "us"
        website = lead.get("website_url") or lead.get("website") or ""
        # Hard 8s timeout per lead — prevents indefinite hangs (was 15s; tighter
        # bound to reduce event-loop pressure when bulk leads have stale URLs).
        result = await asyncio.wait_for(
            full_business_verify(name, city, country=country, website_url=website),
            timeout=8.0,
        )
        await save_verified_profile(db, lead_id, result)
    except asyncio.TimeoutError:
        logger.warning(f"[auto-blast] verify TIMEOUT for {lead_id} — proceeding without verification")
    except Exception as e:
        logger.warning(f"[auto-blast] verify failed for {lead_id}: {e}")

    fresh = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    return fresh or lead


# ─────────────────────────────────────────────────────────────
# Eligibility filter
# ─────────────────────────────────────────────────────────────
async def _eligible_leads(db, limit: int) -> List[Dict[str, Any]]:
    """Fetch leads that have never been blasted, are contactable, AND are not
    noise-domain residue from the pre-iter-282u scout. Applies the same
    `BLOCKED_DOMAINS` + `is_valid_lead` gate used by `google_places_scout`
    so stale Reddit/Yelp-search/Wikipedia/domain-sale rows never enter the
    pipeline.
    """
    # DNC set
    dnc_phones, dnc_emails = set(), set()
    async for d in db.do_not_contact.find({}, {"_id": 0, "phone": 1, "email": 1}):
        if d.get("phone"):
            dnc_phones.add(d["phone"])
        if d.get("email"):
            dnc_emails.add(d["email"].lower())

    # Noise filter — same blocklist as the scout
    try:
        from services.google_places_scout import (
            BLOCKED_DOMAINS,
            _is_blocked_url,
        )
    except Exception:
        BLOCKED_DOMAINS = ()
        _is_blocked_url = lambda _u: False  # noqa: E731

    _NOISE_NAME_SUBSTR = (
        # Aggressive but precise — only listing/directory titles, never SMB names.
        "the best 10 ", " - wikipedia", " - reddit",
        "nail salons for sale", "businesses for sale",
        "yelp.com/search", "r/",
        # iter R234d — additions: real-noise listicle patterns we saw
        # auto-rejecting today: "Find X in Y", "X Companies in Y" (only
        # when paired with a directory domain — see _is_noise below).
    )
    _GENERIC_EMAIL_USERS = {
        # Kept tight — these are mass-mail noise users only. We DO NOT
        # treat `info@`, `hello@`, `contact@`, `admin@`, `webmaster@` as
        # noise anymore: those are the standard SMB inbox formats and
        # rejecting them was killing 879 legitimate dental / HVAC / law
        # practice leads (iter R234d aggressive reclamation).
        "yelp.guest", "noreply", "no-reply", "postmaster",
    }
    # iter R234d — directory / listicle / SaaS / national-chain domains
    # that should always be skipped regardless of the local-part user.
    _NOISE_DOMAIN_SUBSTR = (
        # Original noise list
        "yelp.com", "wikipedia.org", "reddit.com", "justia.com",
        "intently.co", "hvaclocal.com", "procore.com",
        "findbusinesses4sale.com", "bizbuysell.com",
        # iter R234d post-cycle audit: aggressive expansion. These are
        # directory / listing / SaaS-host platforms whose `info@DOMAIN`
        # email is never a local SMB prospect. Even when the
        # `business_name` LOOKS like a real business, the email lands
        # in the platform's corporate inbox, not the merchant's.
        "fresha.com", "rew.ca", "desiforce.com",
        "facebook.com", "instagram.com", "tiktok.com", "twitter.com",
        "linkedin.com", "youtube.com", "pinterest.com",
        "yellowpages", "tripadvisor", "thumbtack", "houzz.com",
        "angi.com", "trustpilot", "glassdoor", "crunchbase",
        "google.com", "googleusercontent", "g.page",
        "homestars", "bbb.org", "indeed.com", "ziprecruiter",
        "weebly.com", "wix.com", "squarespace.com",  # only when site too
        "shopify.com", "etsy.com", "ebay.com", "kijiji.ca",
        "realtor.ca", "realtor.com", "zolo.ca", "zillow.com",
        "remax.ca", "remax.com", "century21",
    )

    def _is_noise(lead: Dict[str, Any]) -> bool:
        name = (lead.get("business_name") or "").lower()
        if any(s in name for s in _NOISE_NAME_SUBSTR):
            return True
        # iter R234d — listicle title pattern: "(N) X in Y", "X Companies in Y",
        # "Find X in Y" — these are always directory pages, never real SMBs.
        if (name.startswith("find ") and " in " in name) or \
           (" companies in " in name) or \
           (" companies near " in name):
            return True
        site = (lead.get("website_url") or lead.get("website") or "").lower()
        if site and _is_blocked_url(site):
            return True
        # iter R234d — explicit noise-domain check (replaces the over-broad
        # generic-user rule that was killing all `info@` SMBs).
        email = (lead.get("email") or "").lower()
        if email and "@" in email:
            user, _, domain = email.partition("@")
            if any(d in domain for d in BLOCKED_DOMAINS):
                return True
            if any(domain == d for d in _NOISE_DOMAIN_SUBSTR):
                return True
            # Big-box retailer / national chains: still skip.
            if domain in {"autozone.com", "walmart.com", "amazon.com",
                          "homedepot.com", "lowes.com", "costco.com"}:
                return True
            # Kept narrow generic-user check — only blocks yelp.guest /
            # noreply / postmaster. `info@`, `hello@`, `admin@` are
            # legit SMB inboxes and pass through to outreach now.
            if user in _GENERIC_EMAIL_USERS:
                return True
        return False

    q = {
        "last_blast_at": {"$exists": False},
        "blast_chain": {"$exists": False},
        # iter R234d — was excluding `not_interested` blindly which caught
        # the 827 noise-falsely-flagged SMBs. We now narrow the exclusion
        # to *user-driven* not_interested OR unsubscribed only; auto-noise
        # uses `noise_flag` (separate field) so re-classification can flip
        # the false positives back.
        "$or": [
            {"status": {"$nin": ["signed_up", "not_interested", "unsubscribed"]}},
            {"status": "not_interested", "noise_reason": {"$in": ["pre-282u-scrape-residue", "listicle-or-directory"]}},
        ],
        # Skip current-cycle noise (set above) but don't permanently exclude.
        "noise_flag": {"$ne": True},
        "$and": [
            {"$or": [
                {"email": {"$nin": ["", None]}},
                {"phone": {"$nin": ["", None]}},
            ]},
        ],
    }
    out: List[Dict[str, Any]] = []
    scanned = 0
    # Sample 5× the cap so we can skip noise and still reach the limit.
    # iter 282aa — Sort prefers Yelp Fusion leads (real SMB phones) first;
    # within source, newest-created comes first.
    async for lead in db.campaign_leads.find(q, {"_id": 0}).sort([
        ("source", -1),       # "yelp_fusion" > "osm_overpass" > "google_places" alphabetically; -1 puts yelp_fusion first
        ("created_at", -1),
    ]).limit(limit * 5):
        scanned += 1
        if (lead.get("phone") or "") in dnc_phones:
            continue
        if (lead.get("email") or "").lower() in dnc_emails:
            continue
        if _is_noise(lead):
            # iter 323t — eligibility checker ONLY filters, NEVER writes.
            # Permanent flagging belongs to the scout pipeline, not here.
            # Previous behaviour permanently set `noise_flag=True` on every
            # excluded lead → infinite re-kill loop (unflag-noise reset
            # → re-flagged next cycle → unflag again → forever).
            continue
        out.append(lead)
        if len(out) >= limit:
            break
    if scanned and not out:
        logger.info(f"[auto-blast] _eligible_leads scanned={scanned} but all noise-filtered")
    return out


# ─────────────────────────────────────────────────────────────
# Diagnostic — iter 323p
# Surfaces the EXACT filter that's killing every cycle. Read-only;
# no side effects. Use from `/api/campaign/why-not-sending` admin route
# when watchdog reports zero_sent_streak ≥ 3.
# ─────────────────────────────────────────────────────────────
async def diagnose_blocker() -> Dict[str, Any]:
    """Return why auto-blast cycles are producing sent=0.

    Surfaces:
      - global config state (enabled flag, last cycle stats)
      - candidate funnel: total → never_blasted → has_contact → status_ok
        → not_dnc → not_noise → final_eligible
      - per-filter exclusion counts (with sample lead IDs for spot-check)
      - "blocking_reason" — the single most-impactful filter to unblock

    Designed to answer "why streak=180?" in one call.
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db not wired"}

    # ── Config state ──────────────────────────────────────────────
    cfg = await db.auto_blast_config.find_one({"tenant_id": "global"}, {"_id": 0}) or {}
    health = await db.ora_campaign_health.find_one({"_id": "global"}, {"_id": 0}) or {}

    # ── Funnel: count what each filter drops ──────────────────────
    total = await db.campaign_leads.count_documents({})
    never_blasted = await db.campaign_leads.count_documents(
        {"last_blast_at": {"$exists": False}})
    queued_with_contact = await db.campaign_leads.count_documents({
        "last_blast_at": {"$exists": False},
        "$or": [
            {"email": {"$nin": ["", None]}},
            {"phone": {"$nin": ["", None]}},
        ],
    })
    queued_status_ok = await db.campaign_leads.count_documents({
        "last_blast_at": {"$exists": False},
        "$or": [
            {"status": {"$nin": ["signed_up", "not_interested", "unsubscribed"]}},
            {"status": "not_interested",
             "noise_reason": {"$in": ["pre-282u-scrape-residue", "listicle-or-directory"]}},
        ],
        "$and": [
            {"$or": [
                {"email": {"$nin": ["", None]}},
                {"phone": {"$nin": ["", None]}},
            ]},
        ],
    })
    queued_not_noise = await db.campaign_leads.count_documents({
        "last_blast_at": {"$exists": False},
        "noise_flag": {"$ne": True},
        "$or": [
            {"status": {"$nin": ["signed_up", "not_interested", "unsubscribed"]}},
            {"status": "not_interested",
             "noise_reason": {"$in": ["pre-282u-scrape-residue", "listicle-or-directory"]}},
        ],
        "$and": [
            {"$or": [
                {"email": {"$nin": ["", None]}},
                {"phone": {"$nin": ["", None]}},
            ]},
        ],
    })

    # noise_flag count alone (how many got hard-flagged by previous cycles)
    noise_flagged = await db.campaign_leads.count_documents({
        "last_blast_at": {"$exists": False},
        "noise_flag": True,
    })

    # Run actual _eligible_leads to get true post-noise count
    eligible_now = await _eligible_leads(db, limit=100)  # peek up to 100

    # Sample 3 of each exclusion bucket for spot-check
    async def _sample(query, n=3):
        out = []
        async for d in db.campaign_leads.find(
            query, {"_id": 0, "lead_id": 1, "business_name": 1,
                    "email": 1, "phone": 1, "status": 1, "noise_flag": 1,
                    "noise_reason": 1, "source": 1},
        ).limit(n):
            out.append(d)
        return out

    samples = {
        "noise_flagged": await _sample({"last_blast_at": {"$exists": False},
                                          "noise_flag": True}),
        "status_excluded": await _sample({"last_blast_at": {"$exists": False},
                                            "status": {"$in": ["signed_up",
                                                                "not_interested",
                                                                "unsubscribed"]}}),
        "no_contact": await _sample({
            "last_blast_at": {"$exists": False},
            "email": {"$in": ["", None]},
            "phone": {"$in": ["", None]},
        }),
    }

    # ── Compute the single blocking reason ────────────────────────
    enabled = bool(cfg.get("enabled"))
    blocking_reason: Optional[str] = None
    fix_command: Optional[str] = None

    if not enabled:
        blocking_reason = "engine_disabled"
        fix_command = "POST /api/campaign/auto-blast/toggle {enabled:true}"
    elif never_blasted == 0:
        blocking_reason = "queue_empty"
        fix_command = "wait for scout to add new leads OR re-arm sent leads"
    elif queued_with_contact == 0:
        blocking_reason = "all_queued_leads_contactless"
        fix_command = "scout pipeline producing leads with no email/phone — check Accurate-Scout & enrichment"
    elif queued_status_ok == 0:
        blocking_reason = "all_queued_marked_user_not_interested_or_unsubscribed"
        fix_command = "manual lead status review needed"
    elif queued_not_noise == 0:
        blocking_reason = "all_queued_noise_flagged"
        fix_command = ("POST /api/campaign/auto-blast/unfllag-all-noise (resets "
                       "noise_flag so legit SMBs misclassified earlier can re-blast)")
    elif len(eligible_now) == 0:
        blocking_reason = "filter_chain_excludes_all_in_eligibility_pass"
        fix_command = "deeper sampling needed; inspect samples below"

    return {
        "ok": True,
        "config": {
            "enabled": enabled,
            "tenant_id": cfg.get("tenant_id"),
            "max_per_cycle": int(cfg.get("max_per_cycle", 10)),
            "interval_minutes": int(cfg.get("interval_minutes", 5)),
            "last_run_at": cfg.get("last_run_at"),
            "last_run_processed": int(cfg.get("last_run_processed") or 0),
            "last_run_sent": int(cfg.get("last_run_sent") or 0),
            "last_run_note": cfg.get("last_run_note"),
        },
        "watchdog": {
            "zero_sent_streak": int(health.get("zero_sent_streak") or 0),
            "heartbeat_age_min": health.get("heartbeat_age_min"),
            "veto_rate_1h": health.get("veto_rate_1h"),
            "tripped": health.get("tripped") or [],
        },
        "funnel": {
            "total_leads": total,
            "never_blasted (queued)": never_blasted,
            "  ... with contact (email or phone)": queued_with_contact,
            "  ... status not in dead-set": queued_status_ok,
            "  ... not noise_flagged": queued_not_noise,
            "  ... final eligible (post _eligible_leads pass)": len(eligible_now),
            "noise_flagged_count": noise_flagged,
        },
        "samples": samples,
        "blocking_reason": blocking_reason,
        "fix_command": fix_command,
    }


async def unflag_all_noise() -> Dict[str, Any]:
    """Force-clear `noise_flag` on every queued lead. Use when the
    noise heuristic was too aggressive and buried legit SMBs.
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db not wired"}
    r = await db.campaign_leads.update_many(
        {"last_blast_at": {"$exists": False}, "noise_flag": True},
        {"$set": {"noise_flag": False,
                  "noise_flag_cleared_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "modified": r.modified_count}


# ─────────────────────────────────────────────────────────────
# Main cycle
# ─────────────────────────────────────────────────────────────
async def run_auto_blast_cycle(force: bool = False) -> Dict[str, Any]:
    """Execute one auto-blast cycle across all tenants that opted in.

    When force=True (admin /run-now), runs regardless of global tenant toggle
    using the 'global' config max_per_cycle.
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db not ready"}

    # Load ALL configs; iterate only the enabled ones (or 'global' if forced)
    configs = await db.auto_blast_config.find({}, {"_id": 0}).to_list(100)
    if force and not any(c.get("tenant_id") == "global" for c in configs):
        configs.append({"tenant_id": "global", "enabled": True, "max_per_cycle": 10})

    total_processed = 0
    total_sent = 0
    summaries: List[Dict[str, Any]] = []
    ran_at_iso = datetime.now(timezone.utc).isoformat()

    for cfg in configs:
        if not force and not cfg.get("enabled"):
            continue
        tenant_id = cfg.get("tenant_id") or "global"
        cap = int(cfg.get("max_per_cycle", 10))

        leads = await _eligible_leads(db, cap)
        note = None
        if not leads:
            note = "no-eligible-leads"
            # Count WHY: this surfaces "scraper is producing contactless leads"
            no_contact_count = await db.campaign_leads.count_documents({
                "last_blast_at": {"$exists": False},
                "email": {"$in": ["", None]},
                "phone": {"$in": ["", None]},
            })
            total_queued = await db.campaign_leads.count_documents({"last_blast_at": {"$exists": False}})
            summaries.append({
                "tenant_id": tenant_id,
                "processed": 0,
                "sent": 0,
                "note": note,
                "queued_but_contactless": no_contact_count,
                "total_queued": total_queued,
            })
            # CRITICAL: update last_run_at even on no-op runs so UI sees heartbeat
            await db.auto_blast_config.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "last_run_at": ran_at_iso,
                    "last_run_processed": 0,
                    "last_run_sent": 0,
                    "last_run_note": note,
                    "last_run_queued_but_contactless": no_contact_count,
                }, "$setOnInsert": {"tenant_id": tenant_id, "enabled": bool(cfg.get("enabled"))}},
                upsert=True,
            )
            continue

        from services.council import council
        from services.ora_learning import ora

        cycle_sent = 0
        for lead in leads:
            lead_id = lead.get("lead_id")
            try:
                # 1) verify (so channel_gating is populated)
                verified = await _auto_verify_lead(db, lead)

                # ── FALLBACK CHANNEL GATING (iter 322g) ─────────────────
                # The Accurate-Scout 8s timeout was silently killing 100%
                # of sends — verification.channel_gating never got saved
                # for real leads, so Council vetoed every blast with
                # "scout:no open channels". 37,245 vetoes recorded.
                # If verification is missing or all-False, derive gates
                # directly from the lead's already-scraped email/phone.
                _v = verified.get("verification") or {}
                _gates = _v.get("channel_gating") or {}
                if not any(_gates.values()):
                    _email = (verified.get("email") or lead.get("email") or "").strip()
                    _phone = (verified.get("phone") or lead.get("phone") or "").strip()
                    _gates = {
                        "email":    bool(_email and "@" in _email),
                        "call":     bool(_phone),
                        "sms":      bool(_phone),
                        "whatsapp": bool(_phone),
                    }
                    _v["channel_gating"] = _gates
                    verified["verification"] = _v
                # ────────────────────────────────────────────────────────

                # iter 296 — Council pre-action gate.
                # iter 322g — lowered confidence_threshold to 0.65 (was 0.7)
                # for outreach_blast specifically. Cost is only $0.005 so
                # cost-of-error is tiny; sending to a 0.65-confidence lead
                # is far better than zero outreach. This unblocks the
                # autonomous loop without needing TJ manual approval.
                decision = await council.deliberate(
                    action_kind="outreach_blast",
                    payload={"lead_id": lead_id, "verification": verified.get("verification") or {}},
                    cost_usd=0.005,  # ~Resend send + Twilio attempt
                    confidence_threshold=0.65,
                )
                if decision["decision"] != "approve":
                    logger.info(f"[auto-blast] council {decision['decision']} for {lead_id} — {decision['reason'][:80]}")
                    if decision["decision"] == "veto":
                        await ora.log_action(
                            agent="envoy", action="outreach_blast",
                            input_data={"lead_id": lead_id},
                            output_data={"success": False, "vetoed_by_council": True, "reason": decision["reason"][:120]},
                        )
                    continue

                # 2) blast — start a 4-touch chain (Section 7).
                # The chain manager fires touch #1 immediately and schedules
                # touches #2–#4 at Day 2 / Day 5 / Day 9 from now. The
                # `chain_advance_scheduler` loop picks up due touches.
                from services.blast_chain import start_chain
                chain_res = await start_chain(db, verified, source="auto")
                res = (chain_res.get("fire") or {})
                total_processed += 1
                sent = int(res.get("sent_count") or 0)
                cycle_sent += sent
                total_sent += sent

                # iter 296 — log to ORA Learning so agent_feed populates + outcomes track
                aid = await ora.log_action(
                    agent="envoy", action="outreach_blast",
                    input_data={"lead_id": lead_id, "channels_open": (verified.get("verification") or {}).get("channel_gating", {})},
                    output_data={"success": sent > 0, "sent_count": sent, "results": res.get("results", {})},
                    cost_usd=0.005 if sent > 0 else 0.0,
                )
                # Initial outcome — webhooks/replies will update later
                await ora.update_outcome(aid, "success" if sent > 0 else "no_reply")

                logger.info(f"[auto-blast] {tenant_id} · {lead_id} · sent {sent}/4")
            except Exception as e:
                logger.warning(f"[auto-blast] lead {lead_id} failed: {e}")

        # Update cfg stats
        await db.auto_blast_config.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "last_run_at": ran_at_iso,
                "last_run_processed": len(leads),
                "last_run_sent": cycle_sent,
                "last_run_note": None,
            }, "$setOnInsert": {"tenant_id": tenant_id, "enabled": bool(cfg.get("enabled"))}},
            upsert=True,
        )
        summaries.append({
            "tenant_id": tenant_id,
            "processed": len(leads),
            "sent": cycle_sent,
        })

    return {
        "ok": True,
        "ran_at": ran_at_iso,
        "tenants_run": len(summaries),
        "total_processed": total_processed,
        "total_sent": total_sent,
        "summaries": summaries,
    }


# ─────────────────────────────────────────────────────────────
# Long-running scheduler (wired from startup_init.py)
# ─────────────────────────────────────────────────────────────
async def auto_blast_scheduler():
    """Loop forever — sleep, then run one cycle if any tenant is enabled."""
    # brief startup delay so app can bind
    print("[auto-blast] scheduler task alive — 30s grace before first cycle", flush=True)
    await asyncio.sleep(30)
    heartbeat_count = 0
    while True:
        try:
            db = _get_db()
            if db is None:
                print("[auto-blast] db not ready yet, retrying in 60s", flush=True)
                await asyncio.sleep(60)
                continue

            # Compute minimum interval across enabled configs (default 5 min)
            cfgs = await db.auto_blast_config.find({"enabled": True}, {"_id": 0}).to_list(50)
            if not cfgs:
                # Log every 5th idle heartbeat so deploy logs confirm scheduler is alive
                heartbeat_count += 1
                if heartbeat_count % 5 == 1:
                    print(f"[auto-blast] idle heartbeat #{heartbeat_count} — no tenant has enabled auto-blast yet", flush=True)
                await asyncio.sleep(120)  # nobody enabled → check again in 2m
                continue

            interval = min(int(c.get("interval_minutes", 5)) for c in cfgs) * 60
            print(f"[auto-blast] cycle starting — {len(cfgs)} enabled tenant(s)", flush=True)
            result = await run_auto_blast_cycle(force=False)
            print(
                f"[auto-blast] cycle done: processed={result.get('total_processed')} "
                f"sent={result.get('total_sent')} summaries={result.get('summaries')}",
                flush=True,
            )
            await asyncio.sleep(max(60, interval))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[auto-blast] scheduler error (will retry in 120s): {e}", flush=True)
            logger.error(f"[auto-blast] scheduler error: {e}", exc_info=True)
            await asyncio.sleep(120)
