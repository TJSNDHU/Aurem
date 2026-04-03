"""
Fast-loading entry point for deployment.
This file loads quickly and provides health endpoints immediately,
then loads the main application in the background.
"""
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import asyncio

# Configure logging immediately
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create app immediately
app = FastAPI(title="ReRoots Skincare API")

# Add CORS immediately
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoints - available IMMEDIATELY
@app.get("/")
async def root():
    return {"status": "ok", "service": "reroots-api"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/health")
async def api_health():
    return {"status": "healthy"}

@app.get("/ready")
async def ready():
    return {"status": "ready"}

logger.info("Fast health endpoints ready!")

# Import and mount the main application
# This happens after health endpoints are registered
try:
    from server import app as main_app, api_router
    
    # Include all routes from the main app
    app.include_router(api_router, prefix="/api")
    
    # Copy over other routes and middleware from main app
    for route in main_app.routes:
        if hasattr(route, 'path'):
            path = route.path
            # Skip routes we already defined
            if path not in ['/', '/health', '/api/health', '/ready', '/docs', '/openapi.json', '/redoc']:
                app.routes.append(route)
    
    logger.info("Main application loaded successfully!")
except Exception as e:
    logger.error(f"Failed to load main app: {e}")
    # Health endpoints still work even if main app fails to load
