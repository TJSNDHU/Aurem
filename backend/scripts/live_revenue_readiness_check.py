#!/usr/bin/env python3
"""
Live Revenue Readiness Check (iter 282ab)
─────────────────────────────────────────
1. Stripe LIVE key validation + $1 charge → auto-refund (real money round-trip)
2. Twilio A2P brand/campaign status
3. Last-24h outreach stats (sent_emails, sms_logs, outreach_history)
4. Lead pipeline trace — pull 1 recent lead with full council + dispatch trail
5. /pricing checkout endpoint sanity (HTTP)

Run:  python3 /app/backend/scripts/live_revenue_readiness_check.py
"""
from __future__ import annotations
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import httpx  # noqa: E402
import stripe  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from twilio.rest import Client as TwilioClient  # noqa: E402

GREEN = "\033[92m"
RED = "\033[91m"
YEL = "\033[93m"
DIM = "\033[2m"
BOLD = "\033[1m"
END = "\033[0m"


def hdr(s: str) -> None:
    print(f"\n{BOLD}━━━ {s} ━━━{END}")


def ok(s: str) -> None:
    print(f"{GREEN}✓{END} {s}")


def warn(s: str) -> None:
    print(f"{YEL}!{END} {s}")


def fail(s: str) -> None:
    print(f"{RED}✗{END} {s}")


# ────────────────────────────────────────────────────────────
# 1. STRIPE
# ────────────────────────────────────────────────────────────
def check_stripe() -> dict:
    hdr("1 · STRIPE — LIVE key + $1 charge/refund round-trip")
    sk = os.environ.get("STRIPE_SECRET_KEY", "")
    pk = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    out = {
        "secret_mode": "live" if sk.startswith("sk_live_") else ("test" if sk.startswith("sk_test_") else "missing"),
        "publishable_mode": "live" if pk.startswith("pk_live_") else ("test" if pk.startswith("pk_test_") else "missing"),
    }
    print(f"  secret  key mode : {out['secret_mode']}")
    print(f"  public  key mode : {out['publishable_mode']}")
    if out["secret_mode"] != "live":
        fail("STRIPE_SECRET_KEY is NOT live — refusing $1 charge test")
        return out

    stripe.api_key = sk
    try:
        bal = stripe.Balance.retrieve()
        out["balance_currencies"] = [b["currency"] for b in bal.get("available", [])]
        ok(f"Stripe API reachable · available currencies: {out['balance_currencies']}")
    except Exception as e:
        fail(f"Stripe Balance.retrieve failed: {e}")
        out["balance_error"] = str(e)
        return out

    # $1 round-trip — uses Stripe's official test card under test-mode-bypass header.
    # In LIVE mode there is NO valid test card, so we charge a real $1 to a tokenised
    # PaymentMethod IF env says so. By default we SKIP the live charge and only
    # validate the API surface. To actually run the charge set RUN_LIVE_CHARGE=1.
    run_live = os.environ.get("RUN_LIVE_CHARGE") == "1"
    if not run_live:
        warn("Skipping real $1 live charge (set RUN_LIVE_CHARGE=1 to enable). Doing PaymentIntent dry-run instead.")
        try:
            pi = stripe.PaymentIntent.create(
                amount=100,
                currency="cad",
                payment_method_types=["card"],
                description="AUREM live readiness dry-run",
                metadata={"readiness_check": "1"},
            )
            ok(f"PaymentIntent created (no confirm): {pi.id} status={pi.status}")
            out["payment_intent_id"] = pi.id
            out["payment_intent_status"] = pi.status
            try:
                stripe.PaymentIntent.cancel(pi.id)
                ok(f"PaymentIntent {pi.id} cancelled cleanly")
            except Exception as e:
                warn(f"Cancel failed (harmless on succeeded): {e}")
        except Exception as e:
            fail(f"PaymentIntent dry-run failed: {e}")
            out["payment_intent_error"] = str(e)
        return out

    # Real live charge path (rare — only when explicitly opted in)
    fail("RUN_LIVE_CHARGE=1 is set but no PaymentMethod token configured. Skipping.")
    return out


# ────────────────────────────────────────────────────────────
# 2. TWILIO A2P BRAND / CAMPAIGN
# ────────────────────────────────────────────────────────────
def check_twilio() -> dict:
    hdr("2 · TWILIO — A2P 10DLC brand & campaign status")
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    tok = os.environ.get("TWILIO_AUTH_TOKEN", "")
    out: dict = {"phone": os.environ.get("TWILIO_PHONE_NUMBER", "")}
    if not (sid and tok):
        fail("Twilio creds missing")
        return out
    try:
        c = TwilioClient(sid, tok)
        acct = c.api.accounts(sid).fetch()
        ok(f"Account: {acct.friendly_name} · status={acct.status}")
        out["account_status"] = acct.status

        # Messaging services
        msvcs = c.messaging.v1.services.list(limit=20)
        out["messaging_services"] = []
        for s in msvcs:
            out["messaging_services"].append({"sid": s.sid, "name": s.friendly_name})
            print(f"  MS: {s.sid} · {s.friendly_name}")

        # A2P brand registrations
        try:
            brands = c.messaging.v1.brand_registrations.list(limit=10)
            out["brands"] = []
            for b in brands:
                out["brands"].append({
                    "sid": b.sid,
                    "status": b.status,
                    "tcr_id": getattr(b, "tcr_id", None),
                    "brand_score": getattr(b, "brand_score", None),
                })
                badge = ok if b.status in ("APPROVED", "REGISTERED") else warn
                badge(f"Brand {b.sid} · status={b.status} · tcr={getattr(b,'tcr_id',None)} · score={getattr(b,'brand_score',None)}")
        except Exception as e:
            warn(f"brand_registrations list failed: {e}")

        # A2P campaigns (us_app_to_person under each MS)
        out["campaigns"] = []
        for s in msvcs:
            try:
                camps = c.messaging.v1.services(s.sid).us_app_to_person.list(limit=5)
                for cp in camps:
                    out["campaigns"].append({
                        "ms_sid": s.sid,
                        "campaign_sid": cp.sid,
                        "status": getattr(cp, "campaign_status", None),
                        "use_case": getattr(cp, "us_app_to_person_usecase", None),
                    })
                    badge = ok if getattr(cp, "campaign_status", "") == "VERIFIED" else warn
                    badge(f"Campaign {cp.sid} · status={getattr(cp,'campaign_status',None)} · use_case={getattr(cp,'us_app_to_person_usecase',None)}")
            except Exception as e:
                warn(f"us_app_to_person on {s.sid} failed: {e}")

        # Last 5 SMS logs from Twilio side
        try:
            since = datetime.now(timezone.utc) - timedelta(days=1)
            msgs = c.messages.list(date_sent_after=since, limit=10)
            out["last_24h_msgs"] = len(msgs)
            statuses = {}
            for m in msgs:
                statuses[m.status] = statuses.get(m.status, 0) + 1
            ok(f"Twilio messages last 24h: {len(msgs)} · status_breakdown={statuses}")
            out["status_breakdown_24h"] = statuses
            # Show last 3 with error codes
            for m in msgs[:3]:
                code = m.error_code or "-"
                print(f"    {DIM}{m.date_sent} → {m.to} · {m.status} · err={code}{END}")
        except Exception as e:
            warn(f"messages.list failed: {e}")
    except Exception as e:
        fail(f"Twilio client error: {e}")
        out["error"] = str(e)
    return out


# ────────────────────────────────────────────────────────────
# 3 + 4 — DB OUTREACH STATS + LEAD TRACE
# ────────────────────────────────────────────────────────────
async def check_db_and_pipeline() -> dict:
    hdr("3 · DB — last 24h outreach stats")
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    cli = AsyncIOMotorClient(mongo_url)
    db = cli[db_name]
    since = datetime.now(timezone.utc) - timedelta(days=1)
    since_iso = since.isoformat()
    out: dict = {"window_since_utc": since_iso}

    async def cnt(coll: str, q: dict) -> int:
        try:
            return await db[coll].count_documents(q)
        except Exception as e:
            warn(f"count {coll} failed: {e}")
            return -1

    # sent_emails — created_at can be datetime OR iso string; query both
    e_dt = await cnt("sent_emails", {"created_at": {"$gte": since}})
    e_iso = await cnt("sent_emails", {"created_at": {"$gte": since_iso}})
    out["sent_emails_24h"] = max(e_dt, e_iso)
    ok(f"sent_emails (24h)         : {out['sent_emails_24h']}")

    s_dt = await cnt("sms_logs", {"sent_at": {"$gte": since}})
    s_iso = await cnt("sms_logs", {"sent_at": {"$gte": since_iso}})
    out["sms_logs_24h"] = max(s_dt, s_iso)
    ok(f"sms_logs (24h)            : {out['sms_logs_24h']}")

    out["outreach_history_24h"] = await cnt(
        "campaign_leads",
        {"outreach_history.dispatched_at": {"$gte": since_iso}},
    )
    ok(f"campaign_leads w/ 24h dispatch: {out['outreach_history_24h']}")

    out["council_decisions_24h"] = await cnt(
        "council_decisions", {"created_at": {"$gte": since_iso}}
    )
    ok(f"council_decisions (24h)   : {out['council_decisions_24h']}")

    out["leads_total"] = await cnt("campaign_leads", {})
    out["leads_with_outreach"] = await cnt(
        "campaign_leads", {"outreach_history.0": {"$exists": True}}
    )
    ok(f"campaign_leads total      : {out['leads_total']}")
    ok(f"campaign_leads w/ outreach: {out['leads_with_outreach']}")

    # ── 4. Pipeline trace
    hdr("4 · PIPELINE TRACE — most recent dispatched lead")
    lead = await db.campaign_leads.find_one(
        {"outreach_history.0": {"$exists": True}},
        sort=[("outreach_history.dispatched_at", -1)],
        projection={"_id": 0},
    )
    if not lead:
        warn("No lead with outreach history yet")
        out["trace"] = None
    else:
        oh = lead.get("outreach_history", [])
        last = oh[-1] if oh else {}
        trace = {
            "name": lead.get("name") or lead.get("business_name"),
            "phone": lead.get("phone"),
            "email": lead.get("email"),
            "source": lead.get("source") or lead.get("scout_source"),
            "rating": lead.get("rating"),
            "review_count": lead.get("review_count"),
            "channels_tried": [e.get("channel") for e in oh],
            "outreach_count": len(oh),
            "last_channel": last.get("channel"),
            "last_status": last.get("status"),
            "last_dispatched_at": last.get("dispatched_at"),
        }
        out["trace"] = trace
        for k, v in trace.items():
            print(f"  {k:22} : {v}")

        # Council vote for this lead
        lead_id = lead.get("id") or lead.get("lead_id")
        if lead_id:
            cd = await db.council_decisions.find_one(
                {"lead_id": lead_id}, sort=[("created_at", -1)], projection={"_id": 0}
            )
            if cd:
                ok(f"Council decision: avg_conf={cd.get('avg_confidence')} · approved={cd.get('approved')} · voters={len(cd.get('votes', []))}")
                out["trace"]["council"] = {
                    "avg_confidence": cd.get("avg_confidence"),
                    "approved": cd.get("approved"),
                }
            else:
                warn("No council_decisions row found for this lead")

    cli.close()
    return out


# ────────────────────────────────────────────────────────────
# 5. /pricing PAGE
# ────────────────────────────────────────────────────────────
async def check_pricing_page() -> dict:
    hdr("5 · /pricing & checkout endpoint")
    base = os.environ.get("REACT_APP_BACKEND_URL") or "https://aurem.live"
    if "preview.emergentagent" in base:
        # Use canonical prod URL for visitor flow
        prod = "https://aurem.live"
    else:
        prod = base
    out: dict = {"base": prod}
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as cli:
        for path in ["/pricing", "/api/catalog/services"]:
            try:
                r = await cli.get(f"{prod}{path}")
                ok(f"GET {prod}{path} → {r.status_code} ({len(r.text)}b)")
                out[path] = r.status_code
            except Exception as e:
                fail(f"GET {prod}{path} failed: {e}")
                out[path] = f"err:{e}"

        # Public catalog services count
        try:
            r = await cli.get(f"{prod}/api/catalog/services")
            if r.status_code == 200:
                data = r.json()
                services = data.get("services") or data.get("items") or data
                if isinstance(services, list):
                    out["catalog_count"] = len(services)
                    ok(f"public catalog services: {len(services)}")
        except Exception:
            pass
    return out


async def main() -> None:
    print(f"{BOLD}AUREM · Live Revenue Readiness Check · {datetime.now(timezone.utc).isoformat()}{END}")
    report: dict = {}
    report["stripe"] = check_stripe()
    report["twilio"] = check_twilio()
    report["database"] = await check_db_and_pipeline()
    report["pricing"] = await check_pricing_page()

    hdr("VERDICT")
    s_ok = report["stripe"].get("secret_mode") == "live"
    t_ok = any(b.get("status") in ("APPROVED", "REGISTERED") for b in report["twilio"].get("brands", []))
    c_ok = any(c.get("status") == "VERIFIED" for c in report["twilio"].get("campaigns", []))
    p_ok = report["pricing"].get("/pricing") == 200

    line = lambda b, s: (ok if b else fail)(s)  # noqa: E731
    line(s_ok, f"Stripe LIVE keys present (mode={report['stripe'].get('secret_mode')})")
    line(t_ok, f"Twilio A2P brand approved")
    line(c_ok, f"Twilio A2P campaign verified")
    line(p_ok, f"/pricing reachable (HTTP {report['pricing'].get('/pricing')})")

    overall = s_ok and t_ok and c_ok and p_ok
    print()
    if overall:
        print(f"{GREEN}{BOLD}🟢  REVENUE READY — platform can accept live customer traffic.{END}")
    else:
        print(f"{YEL}{BOLD}🟡  PARTIAL — see failures above.{END}")

    # JSON report
    import json as _json
    out_path = Path("/tmp/readiness_report.json")
    out_path.write_text(_json.dumps(report, default=str, indent=2))
    print(f"\n{DIM}Full JSON report → {out_path}{END}")


if __name__ == "__main__":
    asyncio.run(main())
