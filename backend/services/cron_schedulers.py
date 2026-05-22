"""
Cron Schedulers — Background scheduled tasks for AUREM.
Extracted from server.py for modularity.
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta

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
            return _db
    except Exception:
        pass
    return None


async def daily_stock_alert_scheduler():
    """Daily 8am EST - Alert on low stock products via WhatsApp"""
    import pytz
    est = pytz.timezone('America/Toronto')

    while True:
        db = _get_db()
        try:
            now = datetime.now(est)
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            logging.info(f"[CRON] Stock alert scheduled for {target}, waiting {wait_seconds/3600:.1f}h")
            await asyncio.sleep(wait_seconds)

            if db is None:
                db = _get_db()
            if db is None:
                logging.warning("[CRON] Stock alert: DB not available")
                await asyncio.sleep(3600)
                continue

            low_stock = await db.products.find(
                {"stock": {"$lt": 20, "$gt": 0}},
                {"_id": 0, "name": 1, "stock": 1}
            ).to_list(50)

            out_of_stock = await db.products.find(
                {"stock": {"$lte": 0}},
                {"_id": 0, "name": 1}
            ).to_list(50)

            if low_stock or out_of_stock:
                msg = "\U0001f4e6 *Daily Stock Alert*\n\n"

                if out_of_stock:
                    msg += "\U0001f534 *OUT OF STOCK:*\n"
                    for p in out_of_stock[:10]:
                        msg += f"  - {p['name']}\n"
                    msg += "\n"

                if low_stock:
                    msg += "\U0001f7e1 *LOW STOCK (<20):*\n"
                    for p in low_stock[:10]:
                        msg += f"  - {p['name']}: {p['stock']} left\n"

                try:
                    from services.twilio_service import send_whatsapp_message
                    admin_phone = os.environ.get("ADMIN_WHATSAPP", "+16134000000")
                    await send_whatsapp_message(admin_phone, msg)
                except Exception:
                    pass
                logging.info(f"[CRON] Stock alert sent: {len(low_stock)} low, {len(out_of_stock)} out")
            else:
                logging.info("[CRON] Stock alert: All products well-stocked")

        except Exception as e:
            logging.error(f"[CRON] Stock alert error: {e}")
            await asyncio.sleep(3600)


async def weekly_revenue_summary_scheduler():
    """Weekly Monday 9am EST - Revenue summary via WhatsApp"""
    import pytz
    est = pytz.timezone('America/Toronto')

    while True:
        db = _get_db()
        try:
            now = datetime.now(est)
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0 and now.hour >= 9:
                days_until_monday = 7

            target = (now + timedelta(days=days_until_monday)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )

            wait_seconds = (target - now).total_seconds()
            logging.info(f"[CRON] Revenue summary scheduled for {target}, waiting {wait_seconds/3600:.1f}h")
            await asyncio.sleep(wait_seconds)

            if db is None:
                db = _get_db()
            if db is None:
                await asyncio.sleep(3600)
                continue

            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            orders = await db.orders.find({
                "created_at": {"$gte": week_ago.isoformat()},
                "status": {"$in": ["completed", "shipped", "delivered"]}
            }).to_list(1000)

            total_revenue = sum(o.get("total", 0) for o in orders)
            order_count = len(orders)

            product_counts = {}
            for order in orders:
                for item in order.get("items", []):
                    pid = item.get("product_id", item.get("name", "Unknown"))
                    product_counts[pid] = product_counts.get(pid, 0) + item.get("quantity", 1)

            top_product = max(product_counts.items(), key=lambda x: x[1]) if product_counts else ("N/A", 0)

            msg = f"""*Weekly Revenue Summary*
_Week ending {now.strftime('%B %d, %Y')}_

*Total Revenue:* CAD ${total_revenue:,.2f}
*Orders:* {order_count}
*Top Product:* {top_product[0]} ({top_product[1]} sold)

_AUREM Aesthetics Inc._"""

            try:
                from services.twilio_service import send_whatsapp_message
                admin_phone = os.environ.get("ADMIN_WHATSAPP", "+16134000000")
                await send_whatsapp_message(admin_phone, msg)
            except Exception:
                pass
            logging.info(f"[CRON] Weekly revenue sent: ${total_revenue:.2f}, {order_count} orders")

        except Exception as e:
            logging.error(f"[CRON] Revenue summary error: {e}")
            await asyncio.sleep(3600)


async def cnf_reminder_scheduler():
    """Friday 10am EST - CNF filing reminder until both AURA-GEN products are filed"""
    import pytz
    est = pytz.timezone('America/Toronto')

    while True:
        db = _get_db()
        try:
            now = datetime.now(est)
            days_until_friday = (4 - now.weekday()) % 7
            if days_until_friday == 0 and now.hour >= 10:
                days_until_friday = 7

            target = (now + timedelta(days=days_until_friday)).replace(
                hour=10, minute=0, second=0, microsecond=0
            )

            wait_seconds = (target - now).total_seconds()
            logging.info(f"[CRON] CNF reminder scheduled for {target}, waiting {wait_seconds/3600:.1f}h")
            await asyncio.sleep(wait_seconds)

            if db is None:
                db = _get_db()
            if db is None:
                await asyncio.sleep(3600)
                continue

            auragen_products = await db.products.find({
                "name": {"$regex": "ARC|ACRC|AURA-GEN", "$options": "i"}
            }, {"_id": 0, "name": 1, "cnf_filed": 1}).to_list(10)

            unfiled = [p for p in auragen_products if not p.get("cnf_filed", False)]

            if unfiled:
                msg = "*Health Canada CNF Reminder*\n\nThe following AURA-GEN products do NOT have confirmed CNF filings:\n\n"
                for p in unfiled:
                    msg += f"X {p['name']}\n"
                msg += "\n*DO NOT SELL* these products until CNFs are confirmed.\n\nFile at: https://canada.ca/cosmetic-notification\n_AUREM Aesthetics Inc._"

                try:
                    from services.twilio_service import send_whatsapp_message
                    admin_phone = os.environ.get("ADMIN_WHATSAPP", "+16134000000")
                    await send_whatsapp_message(admin_phone, msg)
                except Exception:
                    pass
                logging.info(f"[CRON] CNF reminder sent: {len(unfiled)} products unfiled")
            else:
                logging.info("[CRON] CNF reminder: All AURA-GEN products filed")
                break

        except Exception as e:
            logging.error(f"[CRON] CNF reminder error: {e}")
            await asyncio.sleep(3600)


async def daily_ora_morning_brief():
    """Iter 322et — 6 AM Toronto founder digest.

    Fetches the same data as `/api/admin/ora-cto/morning-brief` and emails
    the markdown rendering via Resend (when RESEND_API_KEY is set) AND
    optionally WhatsApps a compressed summary to the founder.
    Falls back silently if the email provider isn't configured — the
    digest is still persisted to `ora_morning_briefs` so it's always
    recoverable from the cockpit.
    """
    import pytz
    est = pytz.timezone("America/Toronto")
    while True:
        db = _get_db()
        try:
            now = datetime.now(est)
            target = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now >= target:
                target = target + timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            logging.info(
                f"[CRON] ORA morning brief scheduled for {target}, "
                f"waiting {wait_seconds/3600:.1f}h"
            )
            await asyncio.sleep(wait_seconds)

            if db is None:
                logging.warning("[CRON] morning-brief: db not ready, retry in 1h")
                await asyncio.sleep(3600)
                continue

            # Build the brief by calling the same code path used by the
            # cockpit endpoint — avoids duplication and stays consistent
            # whether the founder runs it manually or it fires at 6 AM.
            from routers.ora_cto_cockpit_router import morning_brief
            # Bypass auth by calling the underlying logic directly. The
            # endpoint factors the auth check at the top, so we replicate
            # only the data-gathering portion via a private helper.
            brief_doc = await _build_morning_brief_inline(db)

            # Persist
            await db.ora_morning_briefs.insert_one({
                "ts":            datetime.now(timezone.utc).isoformat(),
                "target_local":  target.isoformat(),
                "summary":       brief_doc,
            })

            # Email via Resend (best-effort)
            try:
                from services.email_engine import resend  # iter 326x defensive
                api_key = os.environ.get("RESEND_API_KEY", "").strip()
                digest_email = (
                    (await db.platform_settings.find_one({"_id": "ora_cto"}) or {})
                    .get("notifications", {})
                    .get("digest_email")
                    or os.environ.get("FOUNDER_EMAIL", "teji.ss1986@gmail.com")
                )
                if api_key and digest_email:
                    resend.api_key = api_key
                    resend.Emails.send({
                        "from":    os.environ.get("RESEND_FROM",
                                                    "ora@aurem.live"),
                        "to":      [digest_email],
                        "subject": f"☀️ AUREM Morning Brief — {target.strftime('%Y-%m-%d')}",
                        "html":    "<pre style='font-family:ui-monospace,monospace;font-size:12px'>"
                                    + brief_doc["markdown"].replace("<", "&lt;")
                                    + "</pre>",
                    })
                    logging.info("[CRON] ORA morning brief emailed via Resend")
            except Exception as e:
                logging.warning(f"[CRON] morning-brief email skipped: {e}")

            # Sleep 30 min so we don't re-fire on the same hour edge
            await asyncio.sleep(30 * 60)

        except Exception as e:
            logging.error(f"[CRON] morning-brief error: {e}")
            await asyncio.sleep(3600)


async def _build_morning_brief_inline(db):
    """Same data-gathering as routers/ora_cto_cockpit_router.morning_brief,
    callable without an HTTP request. Returns the dict with the markdown
    rendering."""
    import subprocess
    from datetime import timezone as _tz

    try:
        r = subprocess.run(
            ["git", "log", "--pretty=format:%h | %s | %an", "-10"],
            capture_output=True, text=True, timeout=5, cwd="/app",
        )
        git_log_lines = [line for line in (r.stdout or "").splitlines() if line.strip()]
    except Exception:
        git_log_lines = ["(git log unavailable)"]

    pillar_collections = [
        "leads", "customers", "trials", "subscriptions",
        "ora_tool_invocations", "ora_commit_proposals",
        "ora_governance_overrides", "ora_uploaded_files",
        "ora_skills_library", "design_extract_logs",
    ]
    db_counts: dict[str, int] = {}
    for c in pillar_collections:
        try:
            db_counts[c] = await db[c].count_documents({})
        except Exception:
            db_counts[c] = -1

    since = (datetime.now(_tz.utc) - timedelta(hours=24)).isoformat()
    overrides = await db.ora_governance_overrides.find(
        {"ts": {"$gte": since}}, {"_id": 0},
    ).sort("ts", -1).limit(10).to_list(length=10)

    inv_24h = await db.ora_tool_invocations.count_documents({"ts": {"$gte": since}})
    fails_24h = await db.ora_tool_invocations.count_documents(
        {"ts": {"$gte": since}, "ok": False}
    )
    failure_rate = round(fails_24h / max(inv_24h, 1) * 100, 2) if inv_24h else 0.0

    active_customers = 0
    for coll, q in (
        ("subscriptions", {"status": {"$in": ["active", "trialing", "paid"]}}),
        ("customers",     {"status": "active"}),
        ("users",         {"is_active": True}),
    ):
        try:
            n = await db[coll].count_documents(q)
            if n > 0:
                active_customers = n
                break
        except Exception:
            continue

    pending = await db.ora_commit_proposals.find(
        {"status": "pending"}, {"_id": 0},
    ).sort("proposed_at", -1).limit(20).to_list(length=20)

    md_lines = [
        "# AUREM Morning Brief",
        f"_Generated {datetime.now(_tz.utc).isoformat()[:19]} UTC_",
        "",
        "## Last 10 Commits",
    ]
    md_lines.extend([f"  - `{ln}`" for ln in git_log_lines[:10]])
    md_lines += ["", "## DB State"]
    md_lines += [f"  - **{k}** — {v}" for k, v in db_counts.items()]
    md_lines += ["", f"## Council Overrides (24h): {len(overrides)}"]
    if not overrides:
        md_lines.append("  - _no overrides — every council vote honored_")
    md_lines += ["", "## Tool Activity (24h)",
                  f"  - Invocations: **{inv_24h}**",
                  f"  - Failures: **{fails_24h}** ({failure_rate}%)"]
    md_lines += ["", f"## Active Customers: **{active_customers}**"]
    md_lines += ["", f"## Pending Git-Gate Proposals: **{len(pending)}**"]
    if not pending:
        md_lines.append("  - _none — repo is clean_")

    return {
        "git_log":          git_log_lines,
        "db_counts":        db_counts,
        "council_overrides_24h": overrides,
        "tool_activity_24h": {
            "invocations":  inv_24h,
            "failures":     fails_24h,
            "failure_rate": failure_rate,
        },
        "active_customers": active_customers,
        "pending_proposals": pending,
        "markdown":         "\n".join(md_lines),
    }
