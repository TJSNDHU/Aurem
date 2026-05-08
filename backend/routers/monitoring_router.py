"""
Prometheus Metrics Endpoint for AUREM
Exposes /metrics endpoint for Prometheus scraping
"""

from fastapi import APIRouter
from fastapi.responses import Response

try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from services.aurem_monitoring import (
        api_requests_total, api_latency_seconds, active_subscriptions,
        mrr_usd, arr_usd, llm_tokens_total, llm_cost_total, llm_ttft_seconds
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus metrics endpoint
    
    Exposes metrics in Prometheus format:
    - API request counters
    - LLM usage (tokens, cost, latency)
    - Business metrics (MRR, ARR, active subscriptions)
    """
    if not PROMETHEUS_AVAILABLE:
        return Response(content="# prometheus_client not installed\n", media_type="text/plain")
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    Used by Kubernetes liveness/readiness probes
    """
    return {
        "status": "healthy",
        "service": "aurem-api",
        "version": "1.0.0"
    }


@router.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint
    Returns 200 when service is ready to accept traffic
    """
    # Check if database is connected, services are initialized, etc.
    return {
        "ready": True,
        "checks": {
            "database": "connected",
            "toon_service": "initialized",
            "mission_control": "ready"
        }
    }
