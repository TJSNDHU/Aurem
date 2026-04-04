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


# Singleton instance
_dashboard_service = None


def get_dashboard_service(db) -> DashboardService:
    """Get singleton DashboardService instance"""
    global _dashboard_service
    
    if _dashboard_service is None:
        _dashboard_service = DashboardService(db)
    
    return _dashboard_service
