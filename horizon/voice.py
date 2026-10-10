"""ElevenLabs text-to-speech.

Generates a short spoken version of the daily alert so you can listen while
you lace up your shoes. Audio is cached by content hash in ``.cache/audio``.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import httpx

from .config import get_settings

log = logging.getLogger("horizon.voice")

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


def _audio_dir() -> Path:
    settings = get_settings()
    path = Path(settings.cache_dir) / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def synthesize(text: str, voice_id: str | None = None) -> str | None:
    """Return a URL/path to a generated mp3, or None if unavailable."""
    settings = get_settings()
    if not settings.has_elevenlabs:
        log.info("ElevenLabs not configured; skipping audio generation.")
        return None

    digest = hashlib.sha256(
        (voice_id or settings.elevenlabs_voice_id).encode() + text.encode()
    ).hexdigest()[:16]
    out_path = _audio_dir() / f"horizon-{digest}.mp3"
    if out_path.exists():
        return f"/audio/{out_path.name}"

    url = f"{ELEVENLABS_URL}/{voice_id or settings.elevenlabs_voice_id}"
    try:
        resp = httpx.post(
            url,
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "accept": "audio/mpeg",
                "content-type": "application/json",
            },
            json={
                "text": text,
                "model_id": settings.elevenlabs_model,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=settings.llm_timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("ElevenLabs synthesis failed: %s", exc)
        return None

    out_path.write_bytes(resp.content)
    return f"/audio/{out_path.name}"
