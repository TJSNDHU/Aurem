"""
iter 282al-34 — Full AWB E2E test with mock data.
No real lead needed. Reports every step.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

import httpx
from motor.motor_asyncio import AsyncIOMotorClient


TEST_DATA = {
    "business_name": "TJ Auto Clinic",
    "city": "Mississauga",
    "category": "auto_body",
    "phone": "+16134000000",
    "email": "tjautoclinic@gmail.com",
    "website": None,
}


def section(n: int, title: str):
    print(f"\n{'='*68}")
    print(f"STEP {n} — {title}")
    print('='*68)


def ok(msg): print(f"  PASS  ✅  {msg}")
def fail(msg): print(f"  FAIL  ❌  {msg}")
def info(msg): print(f"        ·   {msg}")


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    # iter 282al-34 — AWB internally uses the a2a_task_queue which needs
    # db initialised. Normally this happens inside server startup; in a
    # standalone test we must call it ourselves.
    try:
        from services.a2a_task_queue import set_db as _tq_set_db
        _tq_set_db(db)
    except Exception as _e:
        info(f"task-queue init skipped: {_e}")
    results = {}

    # ============ SETUP: seed a mock lead row ============
    lead_id = f"test-tj-auto-{uuid.uuid4().hex[:8]}"
    mock_lead = {
        "lead_id":       lead_id,
        "business_name": TEST_DATA["business_name"],
        "name":          TEST_DATA["business_name"],
        "city":          TEST_DATA["city"],
        "category":      TEST_DATA["category"],
        "phone":         TEST_DATA["phone"],
        "email":         TEST_DATA["email"],
        "website":       TEST_DATA["website"],
        "source":        "awb_e2e_test",
        "created_at":    datetime.now(timezone.utc).isoformat(),
    }
    await db.campaign_leads.insert_one(mock_lead)

    # ============ STEP 1: Build test site ============
    section(1, "Build test site")
    try:
        from services.auto_website_builder import build_site_for_lead
        t0 = time.perf_counter()
        res = await build_site_for_lead(db, lead_id)
        dt = time.perf_counter() - t0
        if res.get("ok"):
            slug     = res.get("slug")
            live_url = res.get("preview_url") or res.get("live_url") or f"https://aurem.live/api/sites/{slug}"
            site_id  = res.get("site_id")
            ok(f"Site built in {dt:.1f}s")
            info(f"site_id     = {site_id}")
            info(f"slug        = {slug}")
            info(f"live_url    = {live_url}")
            results["step1"] = {"ok": True, "slug": slug, "live_url": live_url, "site_id": site_id, "dt": dt}
        else:
            fail(f"AWB returned ok=False: {res.get('error')}")
            results["step1"] = {"ok": False, "error": res.get("error")}
    except Exception as e:
        import traceback; traceback.print_exc()
        fail(f"exception: {e}")
        results["step1"] = {"ok": False, "error": str(e)}

    # Pull the resulting site row to get theme + final html
    site_doc = None
    slug = results.get("step1", {}).get("slug")
    if slug:
        site_doc = await db.auto_built_sites.find_one(
            {"slug": slug}, {"_id": 0, "html": 0},
        )

    # ============ STEP 2: Check live URL ============
    section(2, "Check live URL")
    if slug:
        API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
        live = f"{API}/api/sites/{slug}"
        info(f"URL probed: {live}")
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(live)
            if r.status_code == 200:
                body = r.text
                has_biz   = TEST_DATA["business_name"] in body or "TJ Auto" in body
                has_phone = "6134000000" in body or "613-400" in body or "(613) 400" in body
                import re
                m = re.search(r"<title[^>]*>([^<]+)</title>", body, re.I)
                title = m.group(1).strip() if m else "(none)"
                if has_biz and has_phone:
                    ok("HTTP 200 · title + biz name + phone visible")
                    results["step2"] = {"ok": True, "status": 200, "title": title,
                                        "biz_visible": has_biz, "phone_visible": has_phone,
                                        "body_size": len(body)}
                else:
                    fail(f"200 but content check failed biz={has_biz} phone={has_phone}")
                    results["step2"] = {"ok": False, "status": 200, "title": title,
                                        "biz_visible": has_biz, "phone_visible": has_phone,
                                        "body_size": len(body)}
                info(f"title       = {title[:120]}")
                info(f"biz_visible = {has_biz}")
                info(f"phone_visible = {has_phone}")
                info(f"body_size   = {len(body)} bytes")
            else:
                fail(f"HTTP {r.status_code}")
                results["step2"] = {"ok": False, "status": r.status_code}
        except Exception as e:
            fail(f"exception: {e}")
            results["step2"] = {"ok": False, "error": str(e)}
    else:
        fail("no slug from step 1 — skipping")

    # ============ STEP 3: Theme selector ============
    section(3, "Theme selector — what exists, do they render differently?")
    try:
        from services.awb_theme_catalog import _PRESETS, get_curated_themes
        avail_niches = sorted(_PRESETS.keys())
        info(f"niches defined:  {', '.join(avail_niches)}")
        info(f"niche count:     {len(avail_niches)}")
        # For 'auto' niche (matches our test), list themes
        auto_themes = get_curated_themes("auto")
        info(f"'auto' niche:    {len(auto_themes)} themes")
        for t in auto_themes:
            info(f"   - {t.get('business_name','?'):22}  bg={t['style']['primary_bg']}  accent={t['style']['accent']}  font={t['style']['heading_font']}")

        # Force-build 3 variants
        info("")
        info("Building 3 variants with distinct style_hints...")
        # Build 3 fresh leads to avoid dedupe cache
        variants = [
            ("Pit Crew (dark industrial)",  "TJ Auto Dark",    "+14165550001",
             {"primary_bg": "#0F1419", "primary_text": "#F2F2F2", "accent": "#FF6B35",
              "heading_color": "#FFFFFF", "body_font": "Inter", "heading_font": "Bebas Neue"}),
            ("Garage Classic (clean blue)", "TJ Auto Classic", "+14165550002",
             {"primary_bg": "#FFFFFF", "primary_text": "#1A1A1A", "accent": "#1E5BFF",
              "heading_color": "#0A2540", "body_font": "Roboto", "heading_font": "Roboto Slab"}),
            ("Heritage Auto (warm family)", "TJ Auto Warm",    "+14165550003",
             {"primary_bg": "#F5F1E8", "primary_text": "#2D1F0F", "accent": "#8B2C0E",
              "heading_color": "#3A1F0A", "body_font": "Lora", "heading_font": "Playfair Display"}),
        ]
        render_sizes = []
        accent_seen  = []
        for label, bname, bphone, style in variants:
            variant_lead_id = f"test-theme-{uuid.uuid4().hex[:8]}"
            vlead = {k: v for k, v in mock_lead.items() if k != "_id"}
            vlead.update({
                "lead_id":       variant_lead_id,
                "business_name": bname,
                "name":          bname,
                "phone":         bphone,
            })
            await db.campaign_leads.insert_one(vlead)
            res2 = await build_site_for_lead(db, variant_lead_id,
                                             style_hint={"style": style})
            if res2.get("ok"):
                row = await db.auto_built_sites.find_one(
                    {"slug": res2.get("slug")}, {"_id": 0, "rendered_html": 1},
                )
                html = (row or {}).get("rendered_html", "") or ""
                size = len(html)
                accent_present = style["accent"] in html or style["accent"].lower() in html.lower()
                render_sizes.append(size)
                accent_seen.append(accent_present)
                ok(f"{label:36} html={size:>5}B  accent_in_html={accent_present}")
            else:
                fail(f"{label}: {res2.get('error')}")
        # Themes render differently if sizes differ OR if accents are distinct
        distinct = len(set(render_sizes)) > 1 or all(accent_seen)
        if distinct:
            ok(f"Themes render distinctly (sizes={render_sizes}, accents embedded={accent_seen})")
        else:
            fail(f"Themes did NOT differentiate (all identical bytes: {render_sizes})")
        results["step3"] = {"ok": distinct, "niches": avail_niches, "auto_themes": len(auto_themes),
                            "render_sizes": render_sizes, "accents_embedded": accent_seen}
    except Exception as e:
        import traceback; traceback.print_exc()
        fail(f"exception: {e}")
        results["step3"] = {"ok": False, "error": str(e)}

    # ============ STEP 4: Shortlink ============
    section(4, "Shortlink test")
    try:
        from services.shortlink_service import create_shortlink
        target = results.get("step1", {}).get("live_url") or "https://aurem.live/"
        sl = await create_shortlink(db, lead_id=lead_id, target_url=target)
        if sl and sl.get("slug"):
            code = sl["slug"]
            info(f"shortcode   = {code}")
            info(f"short_url   = {sl.get('short_url')}")
            API = "http://localhost:8001"
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as c:
                r = await c.get(f"{API}/r/{code}")
            if r.status_code in (301, 302, 307, 308):
                loc = r.headers.get("location") or r.headers.get("Location")
                ok(f"HTTP {r.status_code} redirect → {loc[:100]}")
                results["step4"] = {"ok": True, "code": code, "status": r.status_code, "redirect_to": loc}
            else:
                fail(f"expected 3xx redirect, got {r.status_code}")
                results["step4"] = {"ok": False, "status": r.status_code}
        else:
            fail(f"shortlink create failed: {sl}")
            results["step4"] = {"ok": False, "error": str(sl)}
    except Exception as e:
        import traceback; traceback.print_exc()
        fail(f"exception: {e}")
        results["step4"] = {"ok": False, "error": str(e)}

    # ============ STEP 5: SMS test (CA number) ============
    section(5, "SMS test — Canadian number")
    try:
        from services.ca_numbers import is_canadian_number
        from services.sms_killswitch import is_blocked_destination, is_sms_disabled
        to = TEST_DATA["phone"]
        info(f"Destination {to}  CA={is_canadian_number(to)}")
        info(f"sms_disabled={is_sms_disabled()}  blocked={is_blocked_destination(to)}")

        if is_blocked_destination(to):
            fail(f"SMS would be blocked by kill-switch to {to}")
            results["step5"] = {"ok": False, "reason": "blocked_by_killswitch"}
        else:
            # Send real test SMS via Twilio
            from twilio.rest import Client as TC
            sid = os.environ.get("TWILIO_ACCOUNT_SID")
            tok = os.environ.get("TWILIO_AUTH_TOKEN")
            frm = os.environ.get("TWILIO_PHONE_NUMBER") or os.environ.get("TWILIO_FROM_NUMBER")
            short_url = results.get("step4", {}).get("redirect_to") or \
                        f"https://aurem.live/r/{results.get('step4', {}).get('code','test')}"
            body = f"TJ Auto Clinic — demo site: https://aurem.live/r/{results.get('step4', {}).get('code','test')}"
            info(f"from={frm}  to={to}  body={body[:70]}...")
            client = TC(sid, tok)
            msg = client.messages.create(from_=frm, to=to, body=body)
            ok(f"Twilio accepted SMS")
            info(f"sid          = {msg.sid}")
            info(f"status       = {msg.status}")
            info(f"error_code   = {msg.error_code}")
            info(f"CA confirmed = {is_canadian_number(to)}")
            results["step5"] = {"ok": True, "sid": msg.sid, "status": msg.status,
                                "ca_confirmed": is_canadian_number(to)}
    except Exception as e:
        import traceback; traceback.print_exc()
        fail(f"exception: {e}")
        results["step5"] = {"ok": False, "error": str(e)}

    # ============ STEP 6: QA test ============
    section(6, "test-lab.ai QA test")
    key = os.environ.get("TEST_LAB_API_KEY")
    if not key:
        info("QA skipped — TEST_LAB_API_KEY not set in env.")
        results["step6"] = {"ok": "skipped", "reason": "missing_key"}
    else:
        try:
            from services.site_qa_service import run_site_qa
            site_url = results["step1"].get("live_url")
            res6 = await run_site_qa(db, slug=slug, site_url=site_url)
            if res6.get("ok"):
                ok(f"QA ran — {res6.get('passed_count')}/{res6.get('total_count')} passed")
                results["step6"] = {"ok": True, "passed": res6.get('passed_count'), "total": res6.get('total_count')}
            else:
                fail(f"QA returned ok=False: {res6.get('error')}")
                results["step6"] = {"ok": False, "error": res6.get("error")}
        except Exception as e:
            fail(f"exception: {e}")
            results["step6"] = {"ok": False, "error": str(e)}

    # ============ SUMMARY ============
    print("\n" + "="*68)
    print("SUMMARY")
    print("="*68)
    for k in sorted(results):
        s = results[k]
        emoji = "✅" if s.get("ok") is True else ("⏭" if s.get("ok") == "skipped" else "❌")
        print(f"  {emoji} {k}: {s}")

asyncio.run(main())
