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

_Reroots Aesthetics Inc._"""

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
                msg += "\n*DO NOT SELL* these products until CNFs are confirmed.\n\nFile at: https://canada.ca/cosmetic-notification\n_Reroots Aesthetics Inc._"

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
