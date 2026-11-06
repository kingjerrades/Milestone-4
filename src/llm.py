"""Minimal Gemini client (standard library only).

The API key is read from the GEMINI_API_KEY environment variable, or from a
local .env file during development. On Streamlit Cloud it comes from the app's
Secrets settings. The key is sent in a request header, never in the URL.

    from llm import generate
    text = generate("Say hi", system="Be brief.", model=CLASSIFIER_MODEL)
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CLASSIFIER_MODEL = os.environ.get("MF_CLASSIFIER_MODEL", "gemini-flash-lite-latest")
ANSWER_MODEL = os.environ.get("MF_ANSWER_MODEL", "gemini-flash-lite-latest")
# Tried in order when the main model is busy; each has its own free-tier limits.
BACKUP_MODELS = [m.strip() for m in os.environ.get(
    "MF_BACKUP_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash-lite").split(",") if m.strip()]


class LLMError(RuntimeError):
    pass


def _api_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def available() -> bool:
    return bool(_api_key())


def generate(prompt: str, *, system: str = "", model: str = ANSWER_MODEL,
             temperature: float = 0.0, max_tokens: int = 300, json_mode: bool = False,
             timeout: float = 15) -> str:
    """One prompt in, text out. Raises LLMError on any failure."""
    key = _api_key()
    if not key:
        raise LLMError("GEMINI_API_KEY is not set")

    config = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if json_mode:
        config["responseMimeType"] = "application/json"
    # Keep "thinking" to a minimum: replies stay fast and within free-tier limits.
    config["thinkingConfig"] = {"thinkingLevel": "minimal" if "lite" in model else "low"}
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": config}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    # When Google is busy (429 rate limit / 503 overloaded / timeout), wait and
    # retry, then fall back to a backup model with its own separate limits.
    models = [model] + [m for m in BACKUP_MODELS if m != model]
    waits = [0, 2, 5]
    last = ""
    for m in models:
        for wait in waits:
            time.sleep(wait)
            req = urllib.request.Request(
                API.format(model=m), data=json.dumps(body).encode("utf-8"), method="POST",
                headers={"Content-Type": "application/json", "x-goog-api-key": key},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.load(resp)
                break
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
                if e.code not in (429, 500, 503):
                    raise LLMError(last) from None
            except Exception as e:  # noqa: BLE001  (network error, timeout)
                last = str(e)
        else:
            continue  # every retry on this model failed: try the backup
        break
    else:
        raise LLMError(f"all models busy: {last}")

    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError):
        raise LLMError(f"unexpected response: {str(data)[:300]}") from None
