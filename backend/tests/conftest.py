"""Ensure backend .env is loaded before any test runs."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Default API URL to the FRONTEND's configured backend URL if the
# REACT_APP_BACKEND_URL env var isn't already exported. Hitting the
# external preview URL is critical because middleware/health_probe.py
# returns 204 (instead of the real 401) for every /api/admin/* request
# coming from localhost during the first 90s of boot grace, which made
# the iter 332b D-6/D-7/D-8 negative tests flake during grouped pytest
# runs that triggered hot-reload.
if not os.environ.get("REACT_APP_BACKEND_URL"):
    fe_env = Path("/app/frontend/.env")
    if fe_env.exists():
        for line in fe_env.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                os.environ["REACT_APP_BACKEND_URL"] = (
                    line.split("=", 1)[1].strip()
                )
                break
    os.environ.setdefault("REACT_APP_BACKEND_URL", "http://localhost:8001")
