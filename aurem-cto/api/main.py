import os
import time
import logging
import aiosqlite
import jwt
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from dotenv import load_dotenv

# iter 322ex — sovereign LLM + tool-bridge orchestrator
from services.orchestrator import chat_with_tools
from services.tools_bridge import list_tools as upstream_list_tools

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Fail fast at import. The previous default "dev-secret-change-in-prod"
    # is public in the repo, so any token signed with it would be valid
    # against this service forever.
    raise RuntimeError(
        "JWT_SECRET must be set in the environment for aurem-cto/api"
    )
OUTBOX_DB_PATH = os.getenv("OUTBOX_DB_PATH", "/app/data/outbox.sqlite3")

# Application state
START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    # Startup
    logger.info("ORA CTO Sovereign API starting up...")
    
    # Connect to MongoDB Atlas
    app.state.atlas_reachable = False
    try:
        app.state.mongo_client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        await app.state.mongo_client.admin.command("ping")
        app.state.atlas_reachable = True
        logger.info("✓ MongoDB Atlas connection established")
    except Exception as e:
        logger.warning(f"✗ MongoDB Atlas unreachable (graceful degradation): {e}")
        app.state.mongo_client = None
    
    # Initialize SQLite outbox
    os.makedirs(os.path.dirname(OUTBOX_DB_PATH), exist_ok=True)
    app.state.outbox_db = await aiosqlite.connect(OUTBOX_DB_PATH)
    # iter 322ey — schema must include retry_count + processed_at because
    # the outbox sidecar worker (outbox/worker.py) writes to those columns.
    await app.state.outbox_db.execute("""
        CREATE TABLE IF NOT EXISTS outbox_pending (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at    REAL    NOT NULL,
            status        TEXT    NOT NULL DEFAULT 'pending',
            payload       TEXT    NOT NULL,
            retry_count   INTEGER NOT NULL DEFAULT 0,
            processed_at  TEXT,
            error         TEXT
        )
    """)
    await app.state.outbox_db.commit()
    logger.info(f"✓ SQLite outbox initialized at {OUTBOX_DB_PATH}")
    
    yield
    
    # Shutdown
    logger.info("ORA CTO Sovereign API shutting down...")
    if app.state.mongo_client:
        app.state.mongo_client.close()
    await app.state.outbox_db.close()


app = FastAPI(
    title="ORA CTO Sovereign API",
    version="322ew",
    lifespan=lifespan
)

# CORS configuration
# iter 322ew — Council Gate (security review) flagged broad `allow_headers=*` +
# `allow_credentials=True` as a CSRF amplifier. Locked down to explicit list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aurem.live", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


# Pydantic models
class ChatRequest(BaseModel):
    prompt: str
    max_tool_iters: int = 4


class ChatResponse(BaseModel):
    ok: bool
    content: str
    provider: str
    iterations: int


# JWT authentication dependency
async def verify_admin_token(authorization: Optional[str] = Header(None)) -> dict:
    """Verify JWT token and check is_admin claim."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        
        if not payload.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    uptime_s = time.time() - START_TIME
    
    # Count pending outbox items
    async with app.state.outbox_db.execute(
        "SELECT COUNT(*) FROM outbox_pending WHERE status = 'pending'"
    ) as cursor:
        row = await cursor.fetchone()
        outbox_pending_count = row[0] if row else 0
    
    return {
        "ok": True,
        "service": "ora-cto-sovereign",
        "uptime_s": round(uptime_s, 2),
        "atlas_reachable": app.state.atlas_reachable,
        "outbox_pending_count": outbox_pending_count,
        "version": "322ew"
    }


@app.get("/api/tools/list")
async def list_tools(authorization: Optional[str] = Header(None)):
    """Proxy upstream tool catalog via tools_bridge (iter 322ex).

    Falls back to a static 28-tool stub if upstream is unreachable so the
    Cockpit UI still renders something."""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    try:
        tools = await upstream_list_tools(token)
        if tools:
            return {"ok": True, "tools": tools, "count": len(tools), "source": "upstream"}
    except Exception as e:
        logger.warning(f"upstream tool catalog unreachable: {e!r}")
    # Static fallback
    stub = [
        "grep_codebase", "view_file", "view_dir", "curl_internal", "db_count",
        "db_distinct", "git_log", "health_check", "lint_python", "shell_exec",
        "safe_edit", "restart_service", "peer_review", "code_review",
        "council_safe_edit", "council_shell_exec", "propose_commit",
        "create_file", "create_dir", "append_to_file", "pytest_run",
        "cloudflare_dns_list", "cloudflare_dns_write", "docker_compose",
        "pip_propose", "ora_run_natural", "git_status", "git_diff_path",
    ]
    return {"ok": True, "tools": stub, "count": len(stub), "source": "stub-fallback"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: dict = Depends(verify_admin_token),
    authorization: Optional[str] = Header(None),
):
    """Real LLM + tool-call loop (iter 322ex). Routes through:
       Groq llama-3.3-70b → OpenRouter Haiku → Emergent Claude Sonnet 4.5.
       Tool execution proxied to upstream AUREM via tools_bridge."""
    logger.info(f"Chat from {user.get('email') or user.get('sub','?')}: {request.prompt[:80]}")
    jwt_token = ""
    if authorization and authorization.lower().startswith("bearer "):
        jwt_token = authorization.split(" ", 1)[1].strip()

    res = await chat_with_tools(
        prompt=request.prompt,
        jwt_token=jwt_token,
        max_iters=max(1, min(request.max_tool_iters, 6)),
    )
    return ChatResponse(
        ok=res.get("ok", True),
        content=res.get("content") or "(no response)",
        provider=res.get("provider") or "?",
        iterations=res.get("iterations") or 0,
    )


@app.get("/api/outbox/stats")
async def outbox_stats():
    """Get outbox statistics."""
    stats = {"pending": 0, "processed": 0, "failed": 0}
    
    for status in ["pending", "processed", "failed"]:
        async with app.state.outbox_db.execute(
            "SELECT COUNT(*) FROM outbox_pending WHERE status = ?", (status,)
        ) as cursor:
            row = await cursor.fetchone()
            stats[status] = row[0] if row else 0
    
    return {"ok": True, "stats": stats}