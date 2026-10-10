"""ElevenLabs voice synthesis + caching (offline)."""

import httpx

from horizon import voice
from horizon.config import get_settings


class _Resp:
    content = b"ID3-fake-mp3-bytes"

    def raise_for_status(self):
        return None


def test_disabled_returns_none():
    assert voice.synthesize("hello") is None


def test_synthesis_writes_and_caches(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    get_settings.cache_clear()

    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        calls["n"] += 1
        return _Resp()

    monkeypatch.setattr(httpx, "post", fake_post)

    first = voice.synthesize("Good evening. Go look up.")
    assert first is not None
    assert first.startswith("/audio/") and first.endswith(".mp3")

    # A repeat of the same text is served from the on-disk cache.
    second = voice.synthesize("Good evening. Go look up.")
    assert second == first
    assert calls["n"] == 1

    # Different text produces a different file.
    third = voice.synthesize("Something else entirely")
    assert third != first
    assert calls["n"] == 2


def test_synthesis_failure_returns_none(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    get_settings.cache_clear()

    def boom(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    assert voice.synthesize("hello") is None
