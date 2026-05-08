"""Ensure backend .env is loaded before any test runs."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Default API URL to localhost if not set (CI / local dev)
os.environ.setdefault("REACT_APP_BACKEND_URL", "http://localhost:8001")
