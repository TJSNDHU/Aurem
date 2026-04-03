"""
ReRoots API - Optimized Entry Point
This file provides immediate health check response while loading the main app.
"""
import os
import sys
import logging
import asyncio
from contextlib import asynccontextmanager

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pre-import heavy modules to start loading them
import_task = None

async def preload_modules():
    """Preload heavy modules in background"""
    global main_app_loaded, main_api_router
    try:
        logger.info("Starting background import of main application...")
        # Import in executor to not block
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: __import__('server'))
        logger.info("Main application module loaded!")
    except Exception as e:
        logger.error(f"Failed to preload: {e}")

# Flag to track main app status
main_app_loaded = False
main_api_router = None

@asynccontextmanager
async def lifespan(app):
    """Lifecycle manager - start preloading main app"""
    global main_app_loaded, main_api_router
    logger.info("=== ReRoots API Starting ===")
    
    # Start background loading
    asyncio.create_task(preload_modules())
    
    yield
    
    logger.info("=== ReRoots API Shutting Down ===")

# Create FastAPI app with lifespan
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ReRoots Skincare API",
    lifespan=lifespan
)

# Add CORS middleware immediately
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Cache-Control", "ETag", "Content-Encoding"],
)

# ============= HEALTH ENDPOINTS - RESPOND IMMEDIATELY =============

@app.get("/")
async def root():
    """Root endpoint"""
    return {"status": "ok", "service": "reroots-api", "version": "1.0.0"}

@app.get("/health")
async def health():
    """Health check for deployment"""
    return {"status": "healthy"}

@app.get("/api/health")
async def api_health():
    """API health check"""
    return {"status": "healthy"}

@app.get("/ready")
async def ready():
    """Readiness check"""
    return {"status": "ready"}

logger.info("Health endpoints registered - server ready for health checks!")

# ============= LOAD MAIN APPLICATION =============
# This runs AFTER health endpoints are available

try:
    logger.info("Loading main server module...")
    from server import api_router, db, app as main_app
    
    # Include the main API router
    app.include_router(api_router, prefix="/api")
    logger.info("Main API router mounted successfully!")
    
    # Copy middleware from main app (except CORS which we already added)
    for middleware in main_app.user_middleware:
        if 'CORSMiddleware' not in str(middleware):
            app.add_middleware(middleware.cls, **middleware.kwargs)
    
    main_app_loaded = True
    logger.info("=== ReRoots API Fully Loaded ===")
    
except Exception as e:
    logger.error(f"Failed to load main application: {e}")
    logger.error("Health endpoints still available, but main functionality unavailable")
    import traceback
    traceback.print_exc()
