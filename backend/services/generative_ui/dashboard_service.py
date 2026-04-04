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
    
    def __init__(self, db):
        self.db = db
        self.generator = get_component_generator()
        
        logger.info("[GenUI] Dashboard Service initialized")
    
    async def generate_subscription_dashboard(self) -> Dict[str, Any]:
        """
        Generate subscription analytics dashboard
        
        Components:
        - Total revenue (metric card)
        - Revenue over time (line chart)
        - Plan distribution (pie chart)
        - Recent subscriptions (table)
        """
        try:
            # Get subscription data
            plans = await self.db.subscription_plans.find(
                {"active": True},
                {"_id": 0}
            ).to_list(100)
            
            # Mock revenue data (replace with real data from crypto treasury)
            total_revenue = 11487.0  # From treasury
            revenue_trend = "+15%"
            
            # Component 1: Total Revenue Card
            revenue_card = {
                "type": "metric_card",
                "data": {
                    "value": f"${total_revenue:,.2f}",
                    "label": "Total Revenue",
                    "change": revenue_trend,
                    "trend": "up"
                },
                "config": {
                    "color": "green",
                    "icon": "dollar"
                }
            }
            
            # Component 2: Revenue Over Time (Line Chart)
            # Mock data - replace with real monthly revenue
            revenue_over_time = [
                {"month": "Jan", "revenue": 8500},
                {"month": "Feb", "revenue": 9200},
                {"month": "Mar", "revenue": 10100},
                {"month": "Apr", "revenue": 11487}
            ]
            
            revenue_chart = {
                "type": "line_chart",
                "data": revenue_over_time,
                "config": {
                    "title": "Revenue Trend",
                    "xKey": "month",
                    "yKey": "revenue",
                    "color": "#10b981"
                }
            }
            
            # Component 3: Plan Distribution (Pie Chart)
            plan_distribution = []
            for plan in plans:
                # Mock subscriber counts
                if plan["tier"] == "free":
                    count = 150
                elif plan["tier"] == "starter":
                    count = 45
                elif plan["tier"] == "professional":
                    count = 12
                elif plan["tier"] == "enterprise":
                    count = 3
                else:
                    count = 0
                
                plan_distribution.append({
                    "name": plan["name"],
                    "value": count
                })
            
            plan_chart = {
                "type": "pie_chart",
                "data": plan_distribution,
                "config": {
                    "title": "Subscribers by Plan"
                }
            }
            
            # Component 4: Recent Subscriptions (Table)
            recent_subs = [
                {
                    "user": "john@example.com",
                    "plan": "Starter",
                    "amount": "$99",
                    "date": "2024-04-01",
                    "status": "Active"
                },
                {
                    "user": "jane@example.com",
                    "plan": "Professional",
                    "amount": "$399",
                    "date": "2024-04-02",
                    "status": "Active"
                },
                {
                    "user": "bob@example.com",
                    "plan": "Enterprise",
                    "amount": "$999",
                    "date": "2024-04-03",
                    "status": "Active"
                }
            ]
            
            subs_table = {
                "type": "data_table",
                "data": recent_subs,
                "config": {
                    "title": "Recent Subscriptions"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                revenue_card,
                revenue_chart,
                plan_chart,
                subs_table
            ])
            
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Subscription dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
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
            
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Hooks performance dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_agent_logs_dashboard(self) -> Dict[str, Any]:
        """
        Generate agent execution logs dashboard
        
        Components:
        - Total agents (metric card)
        - Recent executions (metric card)
        - Agent activity (bar chart)
        - Execution history (table)
        """
        try:
            from services.aurem_agents.harness import get_agent_harness
            
            agent_harness = get_agent_harness()
            agents_data = agent_harness.list_agents()
            agents = agents_data.get("agents", [])
            
            # Component 1: Total Agents Card
            agents_card = {
                "type": "metric_card",
                "data": {
                    "value": str(len(agents)),
                    "label": "Available Agents",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "purple"
                }
            }
            
            # Component 2: Recent Executions Card (mock)
            executions_card = {
                "type": "metric_card",
                "data": {
                    "value": "47",
                    "label": "Executions (7d)",
                    "change": "+23%",
                    "trend": "up"
                },
                "config": {
                    "color": "green"
                }
            }
            
            # Component 3: Agent Activity (Bar Chart)
            agent_activity = []
            for agent in agents:
                # Mock execution counts
                if agent["name"] == "Build Fixer":
                    count = 15
                elif agent["name"] == "Code Reviewer":
                    count = 12
                elif agent["name"] == "Security Scanner":
                    count = 10
                elif agent["name"] == "Feature Planner":
                    count = 10
                else:
                    count = 0
                
                agent_activity.append({
                    "name": agent["name"],
                    "executions": count
                })
            
            activity_chart = {
                "type": "bar_chart",
                "data": agent_activity,
                "config": {
                    "title": "Agent Activity (Last 7 Days)",
                    "xKey": "name",
                    "yKey": "executions",
                    "color": "#8b5cf6"
                }
            }
            
            # Component 4: Recent Executions Table (mock)
            recent_executions = [
                {
                    "agent": "Build Fixer",
                    "task": "Fix ImportError in server.py",
                    "status": "✅ Success",
                    "time": "2024-04-04 10:23",
                    "duration": "2.3s"
                },
                {
                    "agent": "Code Reviewer",
                    "task": "Review crypto_treasury_router.py",
                    "status": "✅ Success",
                    "time": "2024-04-04 09:45",
                    "duration": "1.8s"
                },
                {
                    "agent": "Security Scanner",
                    "task": "Scan new API endpoints",
                    "status": "✅ Success",
                    "time": "2024-04-04 08:12",
                    "duration": "3.5s"
                }
            ]
            
            executions_table = {
                "type": "data_table",
                "data": recent_executions,
                "config": {
                    "title": "Recent Executions"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                agents_card,
                executions_card,
                activity_chart,
                executions_table
            ])
            
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Agent logs dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
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
            
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Usage metrics dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_billing_history_dashboard(self, user_id: str) -> Dict[str, Any]:
        """
        Generate billing history dashboard for a user
        
        Components:
        - Total spent (metric card)
        - Next billing (metric card)
        - Spending over time (line chart)
        - Invoice history (table)
        """
        try:
            # Mock billing data
            total_spent = 537.00
            next_billing_date = "2024-05-01"
            next_billing_amount = 99.00
            
            # Component 1: Total Spent Card
            spent_card = {
                "type": "metric_card",
                "data": {
                    "value": f"${total_spent:,.2f}",
                    "label": "Total Spent",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: Next Billing Card
            next_card = {
                "type": "metric_card",
                "data": {
                    "value": f"${next_billing_amount:.2f}",
                    "label": f"Next Billing ({next_billing_date})",
                    "change": None,
                    "trend": "neutral"
                },
                "config": {
                    "color": "orange"
                }
            }
            
            # Component 3: Spending Over Time (Line Chart)
            spending_history = [
                {"month": "Jan", "amount": 99},
                {"month": "Feb", "amount": 99},
                {"month": "Mar", "amount": 99},
                {"month": "Apr", "amount": 240}
            ]
            
            spending_chart = {
                "type": "line_chart",
                "data": spending_history,
                "config": {
                    "title": "Monthly Spending",
                    "xKey": "month",
                    "yKey": "amount",
                    "color": "#ef4444"
                }
            }
            
            # Component 4: Invoice History (Table)
            invoices = [
                {
                    "date": "2024-04-01",
                    "description": "Starter Plan (Monthly)",
                    "amount": "$99.00",
                    "status": "✅ Paid"
                },
                {
                    "date": "2024-03-01",
                    "description": "Starter Plan (Monthly)",
                    "amount": "$99.00",
                    "status": "✅ Paid"
                },
                {
                    "date": "2024-02-01",
                    "description": "Starter Plan (Monthly)",
                    "amount": "$99.00",
                    "status": "✅ Paid"
                },
                {
                    "date": "2024-01-15",
                    "description": "Setup Fee",
                    "amount": "$240.00",
                    "status": "✅ Paid"
                }
            ]
            
            invoice_table = {
                "type": "data_table",
                "data": invoices,
                "config": {
                    "title": "Invoice History"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                spent_card,
                next_card,
                spending_chart,
                invoice_table
            ])
            
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Billing history dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
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
            
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Performance metrics dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_error_logs_dashboard(self) -> Dict[str, Any]:
        """
        Generate error log analyzer dashboard
        
        Components:
        - Total errors (metric card)
        - Error rate (metric card)
        - Errors over time (line chart)
        - Recent errors (table)
        """
        try:
            # Mock error data
            total_errors = 23
            error_rate = 0.15  # %
            
            # Component 1: Total Errors Card
            errors_card = {
                "type": "metric_card",
                "data": {
                    "value": str(total_errors),
                    "label": "Errors (24h)",
                    "change": "-45%",
                    "trend": "up"
                },
                "config": {
                    "color": "red"
                }
            }
            
            # Component 2: Error Rate Card
            rate_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{error_rate}%",
                    "label": "Error Rate",
                    "change": "-0.08%",
                    "trend": "up"
                },
                "config": {
                    "color": "orange"
                }
            }
            
            # Component 3: Errors Over Time (Line Chart)
            error_timeline = [
                {"hour": "6h ago", "count": 5},
                {"hour": "5h ago", "count": 3},
                {"hour": "4h ago", "count": 2},
                {"hour": "3h ago", "count": 4},
                {"hour": "2h ago", "count": 6},
                {"hour": "1h ago", "count": 2},
                {"hour": "Now", "count": 1}
            ]
            
            timeline_chart = {
                "type": "line_chart",
                "data": error_timeline,
                "config": {
                    "title": "Errors Over Time",
                    "xKey": "hour",
                    "yKey": "count",
                    "color": "#ef4444"
                }
            }
            
            # Component 4: Recent Errors (Table)
            recent_errors = [
                {
                    "time": "2024-04-04 12:15",
                    "level": "❌ ERROR",
                    "message": "Connection timeout to MongoDB",
                    "file": "database.py:45"
                },
                {
                    "time": "2024-04-04 11:30",
                    "level": "⚠️ WARNING",
                    "message": "Slow query detected (>1s)",
                    "file": "treasury_service.py:234"
                },
                {
                    "time": "2024-04-04 10:45",
                    "level": "❌ ERROR",
                    "message": "API rate limit exceeded",
                    "file": "connector_ecosystem.py:567"
                }
            ]
            
            errors_table = {
                "type": "data_table",
                "data": recent_errors,
                "config": {
                    "title": "Recent Errors"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                errors_card,
                rate_card,
                timeline_chart,
                errors_table
            ])
            
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Error logs dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_deployment_history_dashboard(self) -> Dict[str, Any]:
        """
        Generate deployment history dashboard
        
        Components:
        - Total deployments (metric card)
        - Success rate (metric card)
        - Deployment frequency (line chart)
        - Recent deployments (table)
        """
        try:
            # Mock deployment data
            total_deployments = 47
            success_rate = 95.7  # %
            
            # Component 1: Total Deployments Card
            deployments_card = {
                "type": "metric_card",
                "data": {
                    "value": str(total_deployments),
                    "label": "Total Deployments",
                    "change": "+5",
                    "trend": "up"
                },
                "config": {
                    "color": "blue"
                }
            }
            
            # Component 2: Success Rate Card
            success_card = {
                "type": "metric_card",
                "data": {
                    "value": f"{success_rate}%",
                    "label": "Success Rate",
                    "change": "+2.3%",
                    "trend": "up"
                },
                "config": {
                    "color": "green"
                }
            }
            
            # Component 3: Deployment Frequency (Line Chart)
            deployment_freq = [
                {"week": "Week 1", "deploys": 8},
                {"week": "Week 2", "deploys": 12},
                {"week": "Week 3", "deploys": 10},
                {"week": "Week 4", "deploys": 17}
            ]
            
            freq_chart = {
                "type": "line_chart",
                "data": deployment_freq,
                "config": {
                    "title": "Deployments per Week",
                    "xKey": "week",
                    "yKey": "deploys",
                    "color": "#8b5cf6"
                }
            }
            
            # Component 4: Recent Deployments (Table)
            recent_deploys = [
                {
                    "date": "2024-04-04 12:00",
                    "version": "v2.5.3",
                    "status": "✅ Success",
                    "duration": "3m 45s",
                    "deployed_by": "CI/CD"
                },
                {
                    "date": "2024-04-03 15:30",
                    "version": "v2.5.2",
                    "status": "✅ Success",
                    "duration": "4m 12s",
                    "deployed_by": "CI/CD"
                },
                {
                    "date": "2024-04-02 10:15",
                    "version": "v2.5.1",
                    "status": "❌ Failed",
                    "duration": "1m 23s",
                    "deployed_by": "Manual"
                },
                {
                    "date": "2024-04-01 14:45",
                    "version": "v2.5.0",
                    "status": "✅ Success",
                    "duration": "5m 01s",
                    "deployed_by": "CI/CD"
                }
            ]
            
            deploys_table = {
                "type": "data_table",
                "data": recent_deploys,
                "config": {
                    "title": "Recent Deployments"
                }
            }
            
            # Generate dashboard
            dashboard = self.generator.generate_dashboard([
                deployments_card,
                success_card,
                freq_chart,
                deploys_table
            ])
            
            return dashboard
        
        except Exception as e:
            logger.error(f"[GenUI] Deployment history dashboard error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
_dashboard_service = None


def get_dashboard_service(db) -> DashboardService:
    """Get singleton DashboardService instance"""
    global _dashboard_service
    
    if _dashboard_service is None:
        _dashboard_service = DashboardService(db)
    
    return _dashboard_service
