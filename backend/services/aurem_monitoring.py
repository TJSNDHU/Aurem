"""
AUREM Production Monitoring
Prometheus metrics + Grafana dashboards

Based on: AI DevOps Master Blueprint
Tracks:
- Tokens per second
- Time to first token (TTFT)
- API latency
- Cost per request
- Error rates
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from typing import Optional
import time
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# PROMETHEUS METRICS
# ═══════════════════════════════════════════════════════════════════════════════

# Request counters
api_requests_total = Counter(
    'aurem_api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status']
)

# LLM usage
llm_tokens_total = Counter(
    'aurem_llm_tokens_total',
    'Total LLM tokens used',
    ['service', 'model', 'user_tier']
)

llm_cost_total = Counter(
    'aurem_llm_cost_usd_total',
    'Total LLM cost in USD',
    ['service', 'model']
)

# Latency
api_latency_seconds = Histogram(
    'aurem_api_latency_seconds',
    'API request latency',
    ['endpoint'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)

llm_ttft_seconds = Histogram(
    'aurem_llm_ttft_seconds',
    'Time to first token (LLM)',
    ['service', 'model'],
    buckets=(0.1, 0.3, 0.5, 1.0, 2.0, 5.0)
)

llm_total_time_seconds = Histogram(
    'aurem_llm_total_time_seconds',
    'Total LLM generation time',
    ['service', 'model'],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

# Active subscriptions
active_subscriptions = Gauge(
    'aurem_active_subscriptions',
    'Number of active subscriptions',
    ['tier']
)

# Revenue
mrr_usd = Gauge(
    'aurem_mrr_usd',
    'Monthly Recurring Revenue in USD'
)

arr_usd = Gauge(
    'aurem_arr_usd',
    'Annual Recurring Revenue in USD'
)

# System info
aurem_info = Info(
    'aurem_system',
    'AUREM system information'
)

aurem_info.info({
    'version': '1.0.0',
    'format': 'TOON',
    'architecture': 'SaaS + Multi-Agent',
    'python_version': '3.11'
})


# ═══════════════════════════════════════════════════════════════════════════════
# TRACKING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def track_api_request(endpoint: str, method: str, status: int, duration: float):
    """
    Track API request metrics
    
    Args:
        endpoint: API endpoint (e.g., "/api/aurem/chat")
        method: HTTP method (GET, POST, etc.)
        status: HTTP status code
        duration: Request duration in seconds
    """
    api_requests_total.labels(endpoint=endpoint, method=method, status=status).inc()
    api_latency_seconds.labels(endpoint=endpoint).observe(duration)


def track_llm_usage(
    service: str,
    model: str,
    tokens: int,
    cost_usd: float,
    user_tier: str = "free",
    ttft: Optional[float] = None,
    total_time: Optional[float] = None
):
    """
    Track LLM usage metrics
    
    Args:
        service: Service name (e.g., "gpt-4o", "claude-sonnet-4")
        model: Model name
        tokens: Number of tokens used
        cost_usd: Cost in USD
        user_tier: User's subscription tier
        ttft: Time to first token (optional)
        total_time: Total generation time (optional)
    """
    llm_tokens_total.labels(service=service, model=model, user_tier=user_tier).inc(tokens)
    llm_cost_total.labels(service=service, model=model).inc(cost_usd)
    
    if ttft is not None:
        llm_ttft_seconds.labels(service=service, model=model).observe(ttft)
    
    if total_time is not None:
        llm_total_time_seconds.labels(service=service, model=model).observe(total_time)


def update_subscription_metrics(tier_counts: dict, mrr: float):
    """
    Update subscription metrics
    
    Args:
        tier_counts: Dict of {tier: count} (e.g., {"free": 100, "starter": 50})
        mrr: Monthly recurring revenue
    """
    for tier, count in tier_counts.items():
        active_subscriptions.labels(tier=tier).set(count)
    
    mrr_usd.set(mrr)
    arr_usd.set(mrr * 12)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT MANAGER FOR TIMING
# ═══════════════════════════════════════════════════════════════════════════════

class MetricsTimer:
    """Context manager for timing operations"""
    
    def __init__(self, metric: Histogram, labels: dict):
        self.metric = metric
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.metric.labels(**self.labels).observe(duration)
        return False


# Example usage:
# with MetricsTimer(api_latency_seconds, {"endpoint": "/api/chat"}):
#     # Do API call
#     pass


# ═══════════════════════════════════════════════════════════════════════════════
# GRAFANA DASHBOARD JSON EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

GRAFANA_DASHBOARD = {
    "dashboard": {
        "title": "AUREM AI - Production Metrics",
        "panels": [
            {
                "title": "API Requests/sec",
                "targets": [
                    {
                        "expr": "rate(aurem_api_requests_total[5m])"
                    }
                ]
            },
            {
                "title": "LLM Tokens/sec",
                "targets": [
                    {
                        "expr": "rate(aurem_llm_tokens_total[5m])"
                    }
                ]
            },
            {
                "title": "Time to First Token (p95)",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, aurem_llm_ttft_seconds)"
                    }
                ]
            },
            {
                "title": "API Latency (p95)",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, aurem_api_latency_seconds)"
                    }
                ]
            },
            {
                "title": "LLM Cost/hour",
                "targets": [
                    {
                        "expr": "rate(aurem_llm_cost_usd_total[1h]) * 3600"
                    }
                ]
            },
            {
                "title": "Active Subscriptions by Tier",
                "targets": [
                    {
                        "expr": "aurem_active_subscriptions"
                    }
                ]
            },
            {
                "title": "MRR/ARR",
                "targets": [
                    {
                        "expr": "aurem_mrr_usd"
                    },
                    {
                        "expr": "aurem_arr_usd"
                    }
                ]
            }
        ]
    }
}


def export_grafana_dashboard() -> dict:
    """Export Grafana dashboard configuration"""
    return GRAFANA_DASHBOARD
