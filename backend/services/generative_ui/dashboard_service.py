"""
Dashboard Service
Generates pre-built dashboards from AUREM data
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from services.generative_ui.component_generator import get_component_generator

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Service to generate dashboards from AUREM data
    """
    
    # Statuses considered "paid" across the two writers in the codebase
    # (Stripe-flavour values present on either `status` or `payment_status`).
    _PAID_STATUSES = ["paid", "succeeded", "complete", "completed"]

    def __init__(self, db):
        self.db = db
        self.generator = get_component_generator()
        
        logger.info("[GenUI] Dashboard Service initialized")

    # ─────────────────────────────────────────────────────────────────
    # Real-data helpers (Mongo-backed). Used by dashboards that have a
    # canonical source collection. Widgets without a real source still
    # surface a `mock=True` flag in their dashboard payload so consumers
    # can render a "placeholder data" badge.
    # ─────────────────────────────────────────────────────────────────

    def _paid_filter(self) -> Dict[str, Any]:
        return {
            "$or": [
                {"status": {"$in": self._PAID_STATUSES}},
                {"payment_status": {"$in": self._PAID_STATUSES}},
            ]
        }

    async def _sum_revenue(
        self,
        *,
        since_iso: Optional[str] = None,
        until_iso: Optional[str] = None,
        email: Optional[str] = None,
    ) -> tuple[float, str]:
        """Sum `amount` on payment_transactions over a window. Returns (total, currency)."""
        if self.db is None:
            return 0.0, "USD"
        match: Dict[str, Any] = {**self._paid_filter(), "amount": {"$gt": 0}}
        ts: Dict[str, Any] = {}
        if since_iso:
            ts["$gte"] = since_iso
        if until_iso:
            ts["$lt"] = until_iso
        if ts:
            match["created_at"] = ts
        if email:
            match["$and"] = [
                {"$or": [{"email": email}, {"user_email": email}, {"tenant_id": email}]}
            ]
        total = 0.0
        currency = "USD"
        try:
            async for row in self.db.payment_transactions.aggregate([
                {"$match": match},
                {"$group": {
                    "_id": {"$ifNull": ["$currency", "usd"]},
                    "total": {"$sum": "$amount"},
                }},
            ]):
                total += float(row.get("total") or 0)
                currency = (row.get("_id") or "usd").upper()
        except Exception as e:
            logger.warning(f"[GenUI] revenue agg failed: {e}")
        return total, currency

    @staticmethod
    def _month_window(offset_months: int) -> tuple[datetime, datetime, str]:
        """Return (start_dt, end_dt, label) for the calendar month at `offset_months`
        relative to the current month. offset=0 → this month, -1 → last month, etc.
        """
        now = datetime.now(timezone.utc)
        # Anchor on first-of-this-month, then add/subtract months by date math.
        year = now.year
        month = now.month + offset_months
        while month <= 0:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        # End = start of next month
        nm_year, nm_month = (year, month + 1) if month < 12 else (year + 1, 1)
        end = datetime(nm_year, nm_month, 1, tzinfo=timezone.utc)
        return start, end, start.strftime("%b")
    
    async def generate_subscription_dashboard(self) -> Dict[str, Any]:
        """
        Generate subscription analytics dashboard (REAL data — iter 280.4)

        Source collections:
          - subscription_plans         (plan catalogue)
          - customer_subscriptions     (active subs grouped by service_id)
          - payment_transactions       (paid revenue, MTD + 4-month trend)
        """
        try:
            # Plan catalogue
            plans = await self.db.subscription_plans.find(
                {"active": True}, {"_id": 0}
            ).to_list(100)

            # Real revenue: sum of paid payment_transactions for current month.
            month_start, month_end, _ = self._month_window(0)
            total_revenue, currency = await self._sum_revenue(
                since_iso=month_start.isoformat(), until_iso=month_end.isoformat()
            )
            prev_start, prev_end, _ = self._month_window(-1)
            prev_revenue, _ = await self._sum_revenue(
                since_iso=prev_start.isoformat(), until_iso=prev_end.isoformat()
            )
            if prev_revenue > 0:
                change_pct = round(((total_revenue - prev_revenue) / prev_revenue) * 100)
                revenue_trend = f"{'+' if change_pct >= 0 else ''}{change_pct}%"
                trend_dir = "up" if change_pct >= 0 else "down"
            else:
                revenue_trend = None
                trend_dir = "neutral"

            revenue_card = {
                "type": "metric_card",
                "data": {
                    "value": f"${total_revenue:,.2f}",
                    "label": f"Revenue (MTD · {currency})",
                    "change": revenue_trend,
                    "trend": trend_dir,
                },
                "config": {"color": "green", "icon": "dollar"},
            }

            # 4-month trailing revenue trend (oldest → newest, current month last)
            revenue_over_time = []
            for i in range(-3, 1):
                s, e, label = self._month_window(i)
                amt, _ = await self._sum_revenue(
                    since_iso=s.isoformat(), until_iso=e.isoformat()
                )
                revenue_over_time.append({"month": label, "revenue": round(amt, 2)})

            revenue_chart = {
                "type": "line_chart",
                "data": revenue_over_time,
                "config": {
                    "title": "Revenue Trend (last 4 months)",
                    "xKey": "month",
                    "yKey": "revenue",
                    "color": "#10b981",
                },
            }

            # Plan distribution: count active customer_subscriptions grouped
            # by service_id, then map each service_id → human label using the
            # service_name field on the subscription docs themselves.
            plan_distribution: list[Dict[str, Any]] = []
            try:
                async for row in self.db.customer_subscriptions.aggregate([
                    {"$match": {"status": {"$in": ["active", "pending", "trial"]}}},
                    {"$group": {
                        "_id": {"$ifNull": ["$service_name", "$service_id"]},
                        "count": {"$sum": 1},
                    }},
                    {"$sort": {"count": -1}},
                    {"$limit": 12},
                ]):
                    name = row.get("_id") or "Unnamed"
                    plan_distribution.append({"name": str(name), "value": int(row["count"])})
            except Exception as e:
                logger.warning(f"[GenUI] plan distribution agg failed: {e}")

            plan_chart = {
                "type": "pie_chart",
                "data": plan_distribution,
                "config": {"title": "Active Subscriptions by Service"},
            }

            # Recent subscriptions table — last 5 by created/started time.
            recent_subs: list[Dict[str, Any]] = []
            try:
                cursor = self.db.customer_subscriptions.find(
                    {}, {"_id": 0}
                ).sort("started_at", -1).limit(5)
                async for sub in cursor:
                    amt = sub.get("price_monthly") or sub.get("amount") or 0
                    started = sub.get("started_at") or sub.get("created_at") or ""
                    recent_subs.append({
                        "user": sub.get("email", "—"),
                        "plan": sub.get("service_name") or sub.get("service_id") or "—",
                        "amount": f"${float(amt):,.2f}" if amt else "—",
                        "date": str(started)[:10],
                        "status": (sub.get("status") or "—").title(),
                    })
            except Exception as e:
                logger.warning(f"[GenUI] recent subs query failed: {e}")

            subs_table = {
                "type": "data_table",
                "data": recent_subs,
                "config": {"title": "Recent Subscriptions"},
            }

            dashboard = self.generator.generate_dashboard([
                revenue_card, revenue_chart, plan_chart, subs_table,
            ])
            dashboard.setdefault("dashboard", {})["data_source"] = "live"
            dashboard.setdefault("dashboard", {})["plans_known"] = len(plans)
            return dashboard

        except Exception as e:
            logger.error(f"[GenUI] Subscription dashboard error: {e}")
            return {"success": False, "error": str(e)}
    
    async def generate_crypto_treasury_dashboard(self) -> Dict[str, Any]:
        """
        Generate crypto treasury dashboard
        
        Components:
        - Current profit (metric card)
        - Conversion history (line chart)
        - Wallet balance (metric card)
        - Recent transactions (table)
        """
        try:
            # Get treasury stats
            from services.crypto_treasury.treasury_service import get_treasury_service
            
            treasury_service = get_treasury_service(self.db)
            stats = await treasury_service.get_treasury_stats()
            
            # Component 1: Current Profit Card
            profit_card = {
                "type": "metric_card",
                "data": {
                    "value": f"${stats['current_profit_usd']:,.2f}",
                    "label": "Current Profit",
                    "change": "+25%",
                    "trend": "up"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: Wallet Balance Card
            wallet_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{stats['treasury_wallet_balance_usdt']:,.2f} USDT",
                    "label": "Treasury Wallet",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "purple"
                }
            }
            
            # Component 3: Conversion History (Line Chart)
            # Mock data - replace with real conversion history
            conversion_history = [
                {"date": "Week 1", "amount": 0},
                {"date": "Week 2", "amount": 0},
                {"date": "Week 3", "amount": 0},
                {"date": "Week 4", "amount": stats['total_converted_usdt']}
            ]
            
            conversion_chart = {
                "type": "line_chart",
                "data": conversion_history,
                "config": {
                    "title": "USD → USDT Conversions",
                    "xKey": "date",
                    "yKey": "amount",
                    "color": "#8b5cf6"
                }
            }
            
            # Component 4: Recent Transactions (Table)
            transactions = await self.db.crypto_treasury_transactions.find(
                {},
                {"_id": 0}
            ).sort("created_at", -1).limit(5).to_list(5)
            
            # Format for table
            table_data = []
            for tx in transactions:
                table_data.append({
                    "type": tx["transaction_type"],
                    "amount": f"${tx['amount_usd']:.2f}",
                    "status": tx["status"],
                    "date": tx["created_at"].strftime("%Y-%m-%d %H:%M")
                })
            
            tx_table = {
                "type": "data_table",
                "data": table_data,
                "config": {
                    "title": "Recent Transactions"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                profit_card,
                wallet_card,
                conversion_chart,
                tx_table
            ])
            
            dashboard.setdefault("dashboard", {})["data_source"] = "partial"
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Crypto treasury dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_hooks_performance_dashboard(self) -> Dict[str, Any]:
        """
        Generate hooks system performance dashboard
        
        Components:
        - Total executions (metric card)
        - Success rate (metric card)
        - Execution stats by hook (bar chart)
        - Recent hook triggers (table)
        """
        try:
            from services.aurem_hooks.hook_manager import get_hook_manager
            
            hook_manager = get_hook_manager()
            hooks_stats = hook_manager.list_hooks()
            
            # Calculate totals
            total_executions = sum(h.get("executions", 0) for h in hooks_stats)
            active_hooks = sum(1 for h in hooks_stats if h.get("enabled"))
            
            # Component 1: Total Executions Card
            executions_card = {
                "type": "metric_card",
                "data": {
                    "value": str(total_executions),
                    "label": "Total Hook Executions",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: Active Hooks Card
            active_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{active_hooks}/{len(hooks_stats)}",
                    "label": "Active Hooks",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "green"
                }
            }
            
            # Component 3: Executions by Hook (Bar Chart)
            hook_data = []
            for hook in hooks_stats:
                hook_data.append({
                    "name": hook["name"],
                    "executions": hook.get("executions", 0)
                })
            
            # Sort by executions
            hook_data.sort(key=lambda x: x["executions"], reverse=True)
            
            executions_chart = {
                "type": "bar_chart",
                "data": hook_data,
                "config": {
                    "title": "Executions by Hook",
                    "xKey": "name",
                    "yKey": "executions",
                    "color": "#3b82f6"
                }
            }
            
            # Component 4: Hooks Details Table
            table_data = []
            for hook in hooks_stats:
                table_data.append({
                    "hook": hook["name"],
                    "type": hook["type"],
                    "enabled": "✅" if hook.get("enabled") else "❌",
                    "executions": hook.get("executions", 0),
                    "last_run": hook.get("last_execution", "Never")[:19] if hook.get("last_execution") else "Never"
                })
            
            hooks_table = {
                "type": "data_table",
                "data": table_data,
                "config": {
                    "title": "Hooks Overview"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                executions_card,
                active_card,
                executions_chart,
                hooks_table
            ])
            
            dashboard.setdefault("dashboard", {})["data_source"] = "mock"
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Hooks performance dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_agent_logs_dashboard(self) -> Dict[str, Any]:
        """
        Generate agent execution logs dashboard (REAL data — iter 280.4)

        Source: db.activity_feed (live event stream from all 4 pillars).
        - Total agents: distinct `source` values seen in last 30 days.
        - Recent executions (7d): count of events in last 7 days.
        - Activity bar chart: events grouped by `source`.
        - Recent executions table: last 10 raw events.
        """
        try:
            now = datetime.now(timezone.utc)
            cut_7d = now - timedelta(days=7)
            cut_30d = now - timedelta(days=30)

            distinct_sources: list[str] = []
            try:
                distinct_sources = await self.db.activity_feed.distinct(
                    "source", {"timestamp": {"$gte": cut_30d.isoformat()}}
                )
            except Exception as e:
                logger.warning(f"[GenUI] distinct sources failed: {e}")

            executions_7d = 0
            try:
                executions_7d = await self.db.activity_feed.count_documents(
                    {"timestamp": {"$gte": cut_7d.isoformat()}}
                )
            except Exception as e:
                logger.warning(f"[GenUI] activity count failed: {e}")

            agents_card = {
                "type": "metric_card",
                "data": {
                    "value": str(len(distinct_sources)),
                    "label": "Active Agents (30d)",
                    "change": None,
                    "trend": "neutral",
                },
                "config": {"color": "purple"},
            }

            executions_card = {
                "type": "metric_card",
                "data": {
                    "value": str(executions_7d),
                    "label": "Executions (7d)",
                    "change": None,
                    "trend": "neutral",
                },
                "config": {"color": "green"},
            }

            agent_activity: list[Dict[str, Any]] = []
            try:
                async for row in self.db.activity_feed.aggregate([
                    {"$match": {"timestamp": {"$gte": cut_7d.isoformat()}}},
                    {"$group": {"_id": "$source", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 10},
                ]):
                    agent_activity.append({
                        "name": (row.get("_id") or "unknown").title(),
                        "executions": int(row["count"]),
                    })
            except Exception as e:
                logger.warning(f"[GenUI] activity bar agg failed: {e}")

            activity_chart = {
                "type": "bar_chart",
                "data": agent_activity,
                "config": {
                    "title": "Agent Activity (Last 7 Days)",
                    "xKey": "name",
                    "yKey": "executions",
                    "color": "#8b5cf6",
                },
            }

            recent_executions: list[Dict[str, Any]] = []
            try:
                cursor = self.db.activity_feed.find({}, {"_id": 0}).sort("timestamp", -1).limit(10)
                async for ev in cursor:
                    ts_str = str(ev.get("timestamp") or "")[:16].replace("T", " ")
                    recent_executions.append({
                        "agent": (ev.get("source") or "unknown").title(),
                        "task": ev.get("event") or ev.get("business_name") or "—",
                        "status": (ev.get("priority") or "ok").title(),
                        "time": ts_str,
                        "channel": ev.get("channel", "—"),
                    })
            except Exception as e:
                logger.warning(f"[GenUI] recent executions query failed: {e}")

            executions_table = {
                "type": "data_table",
                "data": recent_executions,
                "config": {"title": "Recent Executions"},
            }

            dashboard = self.generator.generate_dashboard([
                agents_card, executions_card, activity_chart, executions_table,
            ])
            dashboard.setdefault("dashboard", {})["data_source"] = "live"
            return dashboard

        except Exception as e:
            logger.error(f"[GenUI] Agent logs dashboard error: {e}")
            return {"success": False, "error": str(e)}
    
    async def generate_connector_stats_dashboard(self) -> Dict[str, Any]:
        """
        Generate connector usage statistics dashboard
        
        Components:
        - Total connectors (metric card)
        - API calls (metric card)
        - Usage by connector (pie chart)
        - Recent connector calls (table)
        """
        try:
            from services.connector_ecosystem import get_connector_ecosystem
            
            connector_service = get_connector_ecosystem()
            connectors = list(connector_service.connectors.keys())
            
            # Component 1: Total Connectors Card
            connectors_card = {
                "type": "metric_card",
                "data": {
                    "value": str(len(connectors)),
                    "label": "Active Connectors",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: API Calls Card (mock)
            calls_card = {
                "type": "metric_card",
                "data": {
                    "value": "1,234",
                    "label": "API Calls (30d)",
                    "change": "+45%",
                    "trend": "up"
                },
                "config": {
                    "color": "green"
                }
            }
            
            # Component 3: Usage by Connector (Pie Chart)
            connector_usage = []
            # Mock usage data
            popular_connectors = [
                ("Reddit", 245),
                ("Twitter", 198),
                ("YouTube", 167),
                ("GitHub", 134),
                ("Google Search", 123),
                ("Others", 367)
            ]
            
            for name, count in popular_connectors:
                connector_usage.append({
                    "name": name,
                    "value": count
                })
            
            usage_chart = {
                "type": "pie_chart",
                "data": connector_usage,
                "config": {
                    "title": "Usage by Connector"
                }
            }
            
            # Component 4: Recent Connector Calls Table
            recent_calls = [
                {
                    "connector": "Reddit",
                    "query": "AI automation",
                    "results": "15",
                    "time": "2024-04-04 11:30",
                    "status": "✅"
                },
                {
                    "connector": "Twitter",
                    "query": "crypto trends",
                    "results": "20",
                    "time": "2024-04-04 11:15",
                    "status": "✅"
                },
                {
                    "connector": "YouTube",
                    "query": "machine learning",
                    "results": "10",
                    "time": "2024-04-04 10:45",
                    "status": "✅"
                }
            ]
            
            calls_table = {
                "type": "data_table",
                "data": recent_calls,
                "config": {
                    "title": "Recent Connector Calls"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                connectors_card,
                calls_card,
                usage_chart,
                calls_table
            ])
            
            dashboard.setdefault("dashboard", {})["data_source"] = "mock"
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Connector stats dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_personal_analytics_dashboard(self, user_id: str) -> Dict[str, Any]:
        """
        Generate personal analytics dashboard for a user
        
        Components:
        - Account age (metric card)
        - Total API calls (metric card)
        - Usage over time (line chart)
        - Feature usage (pie chart)
        """
        try:
            # Mock user data (replace with real user queries)
            account_created = "2024-01-15"
            total_api_calls = 547
            
            # Component 1: Account Age Card
            age_card = {
                "type": "metric_card",
                "data": {
                    "value": "79 days",
                    "label": "Account Age",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: Total API Calls Card
            calls_card = {
                "type": "metric_card",
                "data": {
                    "value": str(total_api_calls),
                    "label": "Total API Calls",
                    "change": "+32%",
                    "trend": "up"
                },
                "config": {
                    "color": "green"
                }
            }
            
            # Component 3: Usage Over Time (Line Chart)
            usage_data = [
                {"week": "Week 1", "calls": 45},
                {"week": "Week 2", "calls": 67},
                {"week": "Week 3", "calls": 89},
                {"week": "Week 4", "calls": 102},
                {"week": "This Week", "calls": 244}
            ]
            
            usage_chart = {
                "type": "line_chart",
                "data": usage_data,
                "config": {
                    "title": "API Usage Trend",
                    "xKey": "week",
                    "yKey": "calls",
                    "color": "#3b82f6"
                }
            }
            
            # Component 4: Feature Usage (Pie Chart)
            feature_usage = [
                {"name": "Connectors", "value": 245},
                {"name": "AI Agents", "value": 167},
                {"name": "Vector Search", "value": 89},
                {"name": "Hooks", "value": 46}
            ]
            
            feature_chart = {
                "type": "pie_chart",
                "data": feature_usage,
                "config": {
                    "title": "Feature Usage Breakdown"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                age_card,
                calls_card,
                usage_chart,
                feature_chart
            ])
            
            dashboard.setdefault("dashboard", {})["data_source"] = "mock"
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Personal analytics dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_pricing_comparison_dashboard(self) -> Dict[str, Any]:
        """
        Generate pricing comparison dashboard
        
        Components:
        - Current plan (metric card)
        - Plan comparison (table)
        - Feature comparison (data visualization)
        - Upgrade savings (metric card)
        """
        try:
            # Get plans
            plans = await self.db.subscription_plans.find(
                {"active": True},
                {"_id": 0}
            ).sort("price_monthly", 1).to_list(10)
            
            # Component 1: Current Plan Card
            current_plan_card = {
                "type": "metric_card",
                "data": {
                    "value": "Starter",
                    "label": "Current Plan",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: Upgrade Savings Card
            savings_card = {
                "type": "metric_card",
                "data": {
                    "value": "$190",
                    "label": "Annual Savings (Pro Plan)",
                    "change": "20% off",
                    "trend": "up"
                },
                "config": {
                    "color": "green"
                }
            }
            
            # Component 3: Plan Comparison Table
            comparison_data = []
            for plan in plans:
                comparison_data.append({
                    "plan": plan["name"],
                    "monthly": f"${plan['price_monthly']}",
                    "annual": f"${plan['price_annual']}",
                    "api_calls": plan.get("api_requests_per_month", "Unlimited"),
                    "features": str(len(plan.get("features", [])))
                })
            
            comparison_table = {
                "type": "data_table",
                "data": comparison_data,
                "config": {
                    "title": "Plan Comparison"
                }
            }
            
            # Component 4: Price Comparison (Bar Chart)
            price_chart_data = []
            for plan in plans:
                if plan["price_monthly"] > 0:
                    price_chart_data.append({
                        "plan": plan["name"],
                        "monthly": plan["price_monthly"],
                        "annual_monthly": round(plan["price_annual"] / 12, 2)
                    })
            
            price_chart = {
                "type": "bar_chart",
                "data": price_chart_data,
                "config": {
                    "title": "Monthly vs Annual Pricing",
                    "xKey": "plan",
                    "yKey": "monthly",
                    "color": "#10b981"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                current_plan_card,
                savings_card,
                comparison_table,
                price_chart
            ])
            
            dashboard.setdefault("dashboard", {})["data_source"] = "static"
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Pricing comparison dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_usage_metrics_dashboard(self, user_id: str) -> Dict[str, Any]:
        """
        Generate usage metrics dashboard for a user
        
        Components:
        - Quota usage (metric card)
        - Remaining quota (metric card)
        - Daily usage (line chart)
        - Top features (bar chart)
        """
        try:
            # Mock usage data
            quota_limit = 10000
            quota_used = 547
            quota_remaining = quota_limit - quota_used
            
            # Component 1: Quota Used Card
            used_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{quota_used:,}",
                    "label": "API Calls Used",
                    "change": f"{(quota_used/quota_limit*100):.1f}% of quota",
                    "trend": "neutral"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: Quota Remaining Card
            remaining_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{quota_remaining:,}",
                    "label": "Calls Remaining",
                    "change": f"{(quota_remaining/quota_limit*100):.1f}% left",
                    "trend": "neutral"
                },
                "config": {
                    "color": "green"
                }
            }
            
            # Component 3: Daily Usage (Line Chart)
            daily_usage = [
                {"day": "Mon", "calls": 67},
                {"day": "Tue", "calls": 89},
                {"day": "Wed", "calls": 102},
                {"day": "Thu", "calls": 134},
                {"day": "Fri", "calls": 155},
                {"day": "Sat", "calls": 0},
                {"day": "Sun", "calls": 0}
            ]
            
            daily_chart = {
                "type": "line_chart",
                "data": daily_usage,
                "config": {
                    "title": "Daily API Usage (This Week)",
                    "xKey": "day",
                    "yKey": "calls",
                    "color": "#8b5cf6"
                }
            }
            
            # Component 4: Top Features (Bar Chart)
            top_features = [
                {"feature": "Connectors", "calls": 245},
                {"feature": "AI Agents", "calls": 167},
                {"feature": "Vector Search", "calls": 89},
                {"feature": "Hooks", "calls": 46}
            ]
            
            features_chart = {
                "type": "bar_chart",
                "data": top_features,
                "config": {
                    "title": "Top Features by Usage",
                    "xKey": "feature",
                    "yKey": "calls",
                    "color": "#f59e0b"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                used_card,
                remaining_card,
                daily_chart,
                features_chart
            ])
            
            dashboard.setdefault("dashboard", {})["data_source"] = "mock"
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Usage metrics dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_billing_history_dashboard(self, user_id: str) -> Dict[str, Any]:
        """
        Generate billing history dashboard for a user (REAL data — iter 280.4)

        `user_id` is treated as the user's email (the canonical identifier
        on payment_transactions: `email`, `user_email`, `tenant_id`).

        Source: db.payment_transactions filtered by paid status + email match.
        """
        try:
            email = (user_id or "").strip().lower()

            # All-time spend for this user
            total_spent, currency = await self._sum_revenue(email=email)

            # Last 4 calendar months trailing spend
            spending_history = []
            for i in range(-3, 1):
                s, e, label = self._month_window(i)
                amt, _ = await self._sum_revenue(
                    since_iso=s.isoformat(), until_iso=e.isoformat(), email=email
                )
                spending_history.append({"month": label, "amount": round(amt, 2)})

            # Most recent paid invoices
            invoices: list[Dict[str, Any]] = []
            next_billing_date = "—"
            next_billing_amount = 0.0
            try:
                match: Dict[str, Any] = {**self._paid_filter()}
                if email:
                    match["$and"] = [{
                        "$or": [{"email": email}, {"user_email": email}, {"tenant_id": email}]
                    }]
                cursor = self.db.payment_transactions.find(
                    match, {"_id": 0}
                ).sort("created_at", -1).limit(10)
                async for tx in cursor:
                    amt = float(tx.get("amount") or 0)
                    cur = (tx.get("currency") or currency).upper()
                    invoices.append({
                        "date": str(tx.get("created_at") or "")[:10],
                        "description": (
                            tx.get("package_name")
                            or tx.get("plan")
                            or tx.get("metadata", {}).get("plan")
                            or "Subscription"
                        ),
                        "amount": f"${amt:,.2f} {cur}",
                        "status": (tx.get("payment_status") or tx.get("status") or "—").title(),
                    })
            except Exception as e:
                logger.warning(f"[GenUI] invoice query failed: {e}")

            # Best-effort "next billing": most recent active subscription's
            # monthly price + first-of-next-month date.
            try:
                sub = await self.db.customer_subscriptions.find_one(
                    {"email": email, "status": {"$in": ["active", "trial"]}},
                    {"_id": 0, "price_monthly": 1, "service_name": 1},
                    sort=[("started_at", -1)],
                )
                if sub:
                    next_billing_amount = float(sub.get("price_monthly") or 0)
                    nxt = self._month_window(1)[0]
                    next_billing_date = nxt.strftime("%Y-%m-%d")
            except Exception as e:
                logger.warning(f"[GenUI] next billing lookup failed: {e}")

            spent_card = {
                "type": "metric_card",
                "data": {
                    "value": f"${total_spent:,.2f}",
                    "label": f"Total Spent ({currency})",
                    "change": None,
                    "trend": "neutral",
                },
                "config": {"color": "blue"},
            }

            next_card = {
                "type": "metric_card",
                "data": {
                    "value": f"${next_billing_amount:,.2f}",
                    "label": f"Next Billing ({next_billing_date})",
                    "change": None,
                    "trend": "neutral",
                },
                "config": {"color": "orange"},
            }

            spending_chart = {
                "type": "line_chart",
                "data": spending_history,
                "config": {
                    "title": "Monthly Spending (last 4 months)",
                    "xKey": "month",
                    "yKey": "amount",
                    "color": "#ef4444",
                },
            }

            invoice_table = {
                "type": "data_table",
                "data": invoices,
                "config": {"title": "Invoice History"},
            }

            dashboard = self.generator.generate_dashboard([
                spent_card, next_card, spending_chart, invoice_table,
            ])
            dashboard.setdefault("dashboard", {})["data_source"] = "live"
            dashboard.setdefault("dashboard", {})["user_id"] = email
            return dashboard

        except Exception as e:
            logger.error(f"[GenUI] Billing history dashboard error: {e}")
            return {"success": False, "error": str(e)}
    
    async def generate_api_tester_dashboard(self) -> Dict[str, Any]:
        """
        Generate API endpoint tester dashboard
        
        Components:
        - Total endpoints (metric card)
        - Response time avg (metric card)
        - Endpoint list with test buttons (table)
        - Response time chart (bar chart)
        """
        try:
            # Mock API endpoint data
            total_endpoints = 147
            avg_response_time = 245  # ms
            
            # Component 1: Total Endpoints Card
            endpoints_card = {
                "type": "metric_card",
                "data": {
                    "value": str(total_endpoints),
                    "label": "Total API Endpoints",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: Avg Response Time Card
            response_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{avg_response_time}ms",
                    "label": "Avg Response Time",
                    "change": "-12%",
                    "trend": "up"
                },
                "config": {
                    "color": "green"
                }
            }
            
            # Component 3: Endpoint List (Table)
            endpoints = [
                {
                    "method": "GET",
                    "endpoint": "/api/generative-ui/dashboards/subscription",
                    "status": "✅ 200",
                    "response_time": "234ms",
                    "last_tested": "2024-04-04 12:00"
                },
                {
                    "method": "POST",
                    "endpoint": "/api/crypto-treasury/convert",
                    "status": "✅ 200",
                    "response_time": "456ms",
                    "last_tested": "2024-04-04 11:45"
                },
                {
                    "method": "GET",
                    "endpoint": "/api/hooks/list",
                    "status": "✅ 200",
                    "response_time": "123ms",
                    "last_tested": "2024-04-04 11:30"
                },
                {
                    "method": "POST",
                    "endpoint": "/api/agents/execute",
                    "status": "✅ 200",
                    "response_time": "678ms",
                    "last_tested": "2024-04-04 11:15"
                }
            ]
            
            endpoints_table = {
                "type": "data_table",
                "data": endpoints,
                "config": {
                    "title": "API Endpoints"
                }
            }
            
            # Component 4: Response Times (Bar Chart)
            response_times = [
                {"endpoint": "dashboards", "time": 234},
                {"endpoint": "crypto", "time": 456},
                {"endpoint": "hooks", "time": 123},
                {"endpoint": "agents", "time": 678}
            ]
            
            response_chart = {
                "type": "bar_chart",
                "data": response_times,
                "config": {
                    "title": "Response Times by Endpoint",
                    "xKey": "endpoint",
                    "yKey": "time",
                    "color": "#3b82f6"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                endpoints_card,
                response_card,
                endpoints_table,
                response_chart
            ])
            
            dashboard.setdefault("dashboard", {})["data_source"] = "static"
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] API tester dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_database_schema_dashboard(self) -> Dict[str, Any]:
        """
        Generate database schema visualizer dashboard
        
        Components:
        - Total collections (metric card)
        - Total documents (metric card)
        - Collection sizes (pie chart)
        - Collections list (table)
        """
        try:
            # Get real collections from MongoDB
            collections = await self.db.list_collection_names()
            total_collections = len(collections)
            
            # Component 1: Total Collections Card
            collections_card = {
                "type": "metric_card",
                "data": {
                    "value": str(total_collections),
                    "label": "Database Collections",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: Total Documents Card (estimated)
            total_docs_card = {
                "type": "metric_card",
                "data": {
                    "value": "12,547",
                    "label": "Total Documents",
                    "change": "+234",
                    "trend": "up"
                },
                "config": {
                    "color": "green"
                }
            }
            
            # Component 3: Top Collections by Size (Pie Chart)
            collection_sizes = [
                {"name": "crypto_treasury_transactions", "value": 2500},
                {"name": "subscription_plans", "value": 450},
                {"name": "users", "value": 1200},
                {"name": "connector_data", "value": 5000},
                {"name": "agent_memory", "value": 3397}
            ]
            
            size_chart = {
                "type": "pie_chart",
                "data": collection_sizes,
                "config": {
                    "title": "Collection Size Distribution"
                }
            }
            
            # Component 4: Collections List (Table)
            collections_list = []
            for coll_name in collections[:10]:  # Limit to 10
                collections_list.append({
                    "collection": coll_name,
                    "type": "MongoDB",
                    "status": "✅ Active",
                    "indexed": "Yes"
                })
            
            collections_table = {
                "type": "data_table",
                "data": collections_list,
                "config": {
                    "title": "Database Collections"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                collections_card,
                total_docs_card,
                size_chart,
                collections_table
            ])
            
            dashboard.setdefault("dashboard", {})["data_source"] = "static"
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Database schema dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_performance_metrics_dashboard(self) -> Dict[str, Any]:
        """
        Generate performance metrics dashboard
        
        Components:
        - CPU usage (metric card)
        - Memory usage (metric card)
        - Request rate (line chart)
        - Slow queries (table)
        """
        try:
            # Mock performance data
            cpu_usage = 45  # %
            memory_usage = 2.3  # GB
            
            # Component 1: CPU Usage Card
            cpu_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{cpu_usage}%",
                    "label": "CPU Usage",
                    "change": "-5%",
                    "trend": "up"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: Memory Usage Card
            memory_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{memory_usage}GB",
                    "label": "Memory Usage",
                    "change": "+0.2GB",
                    "trend": "neutral"
                },
                "config": {
                    "color": "purple"
                }
            }
            
            # Component 3: Request Rate (Line Chart)
            request_rate = [
                {"time": "00:00", "requests": 45},
                {"time": "04:00", "requests": 23},
                {"time": "08:00", "requests": 89},
                {"time": "12:00", "requests": 156},
                {"time": "16:00", "requests": 198},
                {"time": "20:00", "requests": 134},
                {"time": "Now", "requests": 167}
            ]
            
            rate_chart = {
                "type": "line_chart",
                "data": request_rate,
                "config": {
                    "title": "Request Rate (24h)",
                    "xKey": "time",
                    "yKey": "requests",
                    "color": "#10b981"
                }
            }
            
            # Component 4: Slow Queries (Table)
            slow_queries = [
                {
                    "query": "find crypto_treasury_transactions",
                    "duration": "1.2s",
                    "count": "45",
                    "optimization": "Add index"
                },
                {
                    "query": "aggregate connector_data",
                    "duration": "890ms",
                    "count": "23",
                    "optimization": "Use projection"
                },
                {
                    "query": "find users with filter",
                    "duration": "567ms",
                    "count": "12",
                    "optimization": "OK"
                }
            ]
            
            queries_table = {
                "type": "data_table",
                "data": slow_queries,
                "config": {
                    "title": "Slow Queries"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                cpu_card,
                memory_card,
                rate_chart,
                queries_table
            ])
            
            dashboard.setdefault("dashboard", {})["data_source"] = "mock"
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Performance metrics dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_error_logs_dashboard(self) -> Dict[str, Any]:
        """
        Generate error log analyzer dashboard (REAL data — iter 280.4)

        Source: db.client_errors (Sentinel ingest stream).
        - Errors (24h) + 24h delta vs prior 24h
        - Errors over time: hourly buckets across last 7 hours
        - Recent errors table: last 10 events
        """
        try:
            now = datetime.now(timezone.utc)
            cut_24h = now - timedelta(hours=24)
            cut_48h = now - timedelta(hours=48)

            errors_24h = 0
            errors_prev_24h = 0
            try:
                errors_24h = await self.db.client_errors.count_documents(
                    {"ts": {"$gte": cut_24h.isoformat()}}
                )
                errors_prev_24h = await self.db.client_errors.count_documents(
                    {"ts": {"$gte": cut_48h.isoformat(), "$lt": cut_24h.isoformat()}}
                )
            except Exception as e:
                logger.warning(f"[GenUI] error count failed: {e}")

            if errors_prev_24h > 0:
                delta_pct = round(((errors_24h - errors_prev_24h) / errors_prev_24h) * 100)
                change = f"{'+' if delta_pct >= 0 else ''}{delta_pct}%"
                # "trend up" here means "rising count" — UI semantic is up=red for errors
                trend = "up" if delta_pct > 0 else "down"
            else:
                change = None
                trend = "neutral"

            # Error rate = errors_24h / total events. We approximate "events" by
            # capping at activity_feed count (orchestrator-side throughput).
            try:
                throughput = await self.db.activity_feed.count_documents(
                    {"timestamp": {"$gte": cut_24h.isoformat()}}
                )
            except Exception:
                throughput = 0
            error_rate = round((errors_24h / throughput) * 100, 2) if throughput > 0 else 0.0

            errors_card = {
                "type": "metric_card",
                "data": {
                    "value": str(errors_24h),
                    "label": "Errors (24h)",
                    "change": change,
                    "trend": trend,
                },
                "config": {"color": "red"},
            }

            rate_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{error_rate}%",
                    "label": "Error Rate (vs activity)",
                    "change": None,
                    "trend": "neutral",
                },
                "config": {"color": "orange"},
            }

            # Hourly buckets — last 7 hours
            error_timeline = []
            for hr_ago in range(6, -1, -1):
                bucket_end = now - timedelta(hours=hr_ago)
                bucket_start = bucket_end - timedelta(hours=1)
                try:
                    n = await self.db.client_errors.count_documents({
                        "ts": {"$gte": bucket_start.isoformat(), "$lt": bucket_end.isoformat()}
                    })
                except Exception:
                    n = 0
                label = "Now" if hr_ago == 0 else f"{hr_ago}h ago"
                error_timeline.append({"hour": label, "count": int(n)})

            timeline_chart = {
                "type": "line_chart",
                "data": error_timeline,
                "config": {
                    "title": "Errors Over Time (last 7h)",
                    "xKey": "hour",
                    "yKey": "count",
                    "color": "#ef4444",
                },
            }

            recent_errors: list[Dict[str, Any]] = []
            try:
                cursor = self.db.client_errors.find({}, {"_id": 0}).sort("ts", -1).limit(10)
                async for ev in cursor:
                    sc = ev.get("status_code")
                    level = "ERROR" if (sc and int(sc) >= 500) else (
                        "WARNING" if (sc and int(sc) >= 400) else "INFO"
                    )
                    recent_errors.append({
                        "time": str(ev.get("ts") or "")[:19].replace("T", " "),
                        "level": level,
                        "message": (ev.get("message") or "—")[:120],
                        "url": (ev.get("url") or "")[:80],
                    })
            except Exception as e:
                logger.warning(f"[GenUI] recent errors query failed: {e}")

            errors_table = {
                "type": "data_table",
                "data": recent_errors,
                "config": {"title": "Recent Errors"},
            }

            dashboard = self.generator.generate_dashboard([
                errors_card, rate_card, timeline_chart, errors_table,
            ])
            dashboard.setdefault("dashboard", {})["data_source"] = "live"
            return dashboard

        except Exception as e:
            logger.error(f"[GenUI] Error logs dashboard error: {e}")
            return {"success": False, "error": str(e)}
    
    async def generate_deployment_history_dashboard(self) -> Dict[str, Any]:
        """
        Generate deployment history dashboard (REAL data — iter 280.4)

        Source: db.deployment_log (autonomous repair / patch deploy stream).
        - Total deployments: lifetime count
        - Success rate: status='deployed' / total
        - Frequency: per ISO-week buckets across last 4 weeks
        - Recent deployments: last 10 deploy_log rows
        """
        try:
            now = datetime.now(timezone.utc)

            total_deployments = 0
            successes = 0
            try:
                total_deployments = await self.db.deployment_log.estimated_document_count()
                successes = await self.db.deployment_log.count_documents({
                    "status": {"$in": ["deployed", "success", "succeeded", "completed"]}
                })
            except Exception as e:
                logger.warning(f"[GenUI] deploy count failed: {e}")

            success_rate = (
                round((successes / total_deployments) * 100, 1)
                if total_deployments > 0 else 0.0
            )

            deployments_card = {
                "type": "metric_card",
                "data": {
                    "value": str(total_deployments),
                    "label": "Total Deployments",
                    "change": None,
                    "trend": "neutral",
                },
                "config": {"color": "blue"},
            }

            success_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{success_rate}%",
                    "label": "Success Rate",
                    "change": None,
                    "trend": "up" if success_rate >= 90 else "down",
                },
                "config": {"color": "green" if success_rate >= 90 else "orange"},
            }

            # Last 4 weeks frequency.
            deployment_freq = []
            for i in range(3, -1, -1):
                start = now - timedelta(days=(i + 1) * 7)
                end = now - timedelta(days=i * 7)
                try:
                    n = await self.db.deployment_log.count_documents({
                        "$or": [
                            {"created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}},
                            {"timestamp":  {"$gte": start.isoformat(), "$lt": end.isoformat()}},
                            {"deployed_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}},
                        ]
                    })
                except Exception:
                    n = 0
                deployment_freq.append({
                    "week": "Now" if i == 0 else f"-{i}w",
                    "deploys": int(n),
                })

            freq_chart = {
                "type": "line_chart",
                "data": deployment_freq,
                "config": {
                    "title": "Deployments per Week (last 4 weeks)",
                    "xKey": "week",
                    "yKey": "deploys",
                    "color": "#8b5cf6",
                },
            }

            recent_deploys: list[Dict[str, Any]] = []
            try:
                cursor = self.db.deployment_log.find({}, {"_id": 0}).sort("_id", -1).limit(10)
                async for d in cursor:
                    when = (
                        d.get("deployed_at") or d.get("created_at")
                        or d.get("timestamp") or ""
                    )
                    recent_deploys.append({
                        "date": str(when)[:19].replace("T", " "),
                        "version": d.get("deploy_id") or d.get("batch_id") or "—",
                        "status": (d.get("status") or "—").title(),
                        "platform": d.get("platform", "—"),
                        "patches": d.get("patch_count", "—"),
                    })
            except Exception as e:
                logger.warning(f"[GenUI] recent deploys query failed: {e}")

            deploys_table = {
                "type": "data_table",
                "data": recent_deploys,
                "config": {"title": "Recent Deployments"},
            }

            dashboard = self.generator.generate_dashboard([
                deployments_card, success_card, freq_chart, deploys_table,
            ])
            dashboard.setdefault("dashboard", {})["data_source"] = "live"
            return dashboard

        except Exception as e:
            logger.error(f"[GenUI] Deployment history dashboard error: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
_dashboard_service = None


def get_dashboard_service(db) -> DashboardService:
    """Get singleton DashboardService instance"""
    global _dashboard_service
    
    if _dashboard_service is None:
        _dashboard_service = DashboardService(db)
    
    return _dashboard_service
