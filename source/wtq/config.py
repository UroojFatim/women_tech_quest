"""Configuration loaded from environment / .env.

Model is fully configurable so the exact model ID can be swapped without code
changes (e.g. if your API key exposes a slightly different Gemini id).
"""
import os

from dotenv import load_dotenv

load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "google").lower()
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.5-flash-lite")

# Accept several common env var names for the key.
API_KEY = (
    os.getenv("API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or os.getenv("GEMINI_API_KEY")
)

# Determinism + reliability knobs.
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
USE_CACHE = os.getenv("USE_CACHE", "1") != "0"


def require_api_key() -> str:
    if not API_KEY:
        raise SystemExit(
            "No API key found. Copy source/.env.example to source/.env and set "
            "API_KEY=<your Google AI Studio key>."
        )
    return API_KEY
