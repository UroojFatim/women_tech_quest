"""Gemini client wrapper: image+prompt -> parsed JSON, with retry and caching."""
import hashlib
import json
import mimetypes
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from . import config

_client: Optional[genai.Client] = None
_CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"

# Simple counters for the run report.
STATS = {"calls": 0, "cache_hits": 0, "retries": 0}


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.require_api_key())
    return _client


def _cache_path(key: str) -> Path:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return _CACHE_DIR / f"{h}.json"


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _extract_json(text: str) -> Dict[str, Any]:
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the first {...} block.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def generate_json(
    prompt: str,
    image_path: Optional[Path] = None,
    cache_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Call the model and return parsed JSON. Caches by (image bytes + prompt)."""
    _CACHE_DIR.mkdir(exist_ok=True)

    image_bytes = b""
    mime = "image/png"
    if image_path is not None:
        image_bytes = Path(image_path).read_bytes()
        mime = mimetypes.guess_type(str(image_path))[0] or "image/png"

    # Add a short code of the prompt to the cache key. If we change the prompt,
    # the old saved answer is not reused by mistake.
    prompt_sig = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:10]
    key = f"{cache_key}:{prompt_sig}" if cache_key else (
        hashlib.sha256(image_bytes).hexdigest() + "|" + prompt
    )
    cpath = _cache_path(key)
    if config.USE_CACHE and cpath.exists():
        STATS["cache_hits"] += 1
        return json.loads(cpath.read_text(encoding="utf-8"))["parsed"]

    contents: list = []
    if image_path is not None:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime))
    contents.append(prompt)

    cfg = types.GenerateContentConfig(
        temperature=config.TEMPERATURE,
        response_mime_type="application/json",
    )

    last_err: Optional[Exception] = None
    for attempt in range(config.MAX_RETRIES):
        try:
            STATS["calls"] += 1
            resp = _get_client().models.generate_content(
                model=config.MODEL_NAME, contents=contents, config=cfg
            )
            parsed = _extract_json(resp.text or "")
            cpath.write_text(
                json.dumps({"raw": resp.text, "parsed": parsed}, ensure_ascii=False),
                encoding="utf-8",
            )
            return parsed
        except Exception as e:  # noqa: BLE001 - retry if the API has a temporary error
            last_err = e
            msg = str(e).lower()
            transient = any(
                s in msg for s in ("429", "rate", "quota", "503", "500", "unavailable", "timeout")
            )
            if attempt < config.MAX_RETRIES - 1 and transient:
                STATS["retries"] += 1
                time.sleep(min(2 ** attempt * 2, 30))
                continue
            if attempt < config.MAX_RETRIES - 1:
                time.sleep(1)
                continue
            break
    raise RuntimeError(f"LLM call failed after retries: {last_err}")
