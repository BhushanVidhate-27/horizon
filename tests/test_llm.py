"""LLM provider selection and request shaping (fully offline)."""

import httpx

from horizon.config import Settings
from horizon.llm import LLMClient, _ollama_reachable


class _Resp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self._payload


def _settings(**overrides) -> Settings:
    base = {
        "llm_provider": "auto",
        "openrouter_api_key": None,
        "google_api_key": None,
        "hf_api_key": None,
        # Port 9 is almost always closed, but tests monkeypatch reachability anyway.
        "ollama_base_url": "http://localhost:9",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_auto_prefers_ollama_when_reachable(monkeypatch):
    monkeypatch.setattr("horizon.llm._ollama_reachable", lambda url: True)
    client = LLMClient(_settings())
    assert client.provider == "ollama"
    assert client.available and client.model


def test_auto_falls_back_to_none(monkeypatch):
    monkeypatch.setattr("horizon.llm._ollama_reachable", lambda url: False)
    client = LLMClient(_settings())
    assert client.provider == "none"
    assert client.available is False
    assert client.generate("hello") is None


def test_auto_uses_first_available_hosted_key(monkeypatch):
    monkeypatch.setattr("horizon.llm._ollama_reachable", lambda url: False)
    assert LLMClient(_settings(openrouter_api_key="k")).provider == "openrouter"
    assert LLMClient(_settings(google_api_key="k")).provider == "google"
    assert LLMClient(_settings(hf_api_key="k")).provider == "huggingface"


def test_explicit_provider_is_respected():
    client = LLMClient(_settings(llm_provider="google", google_api_key="k"))
    assert client.provider == "google"
    assert client.model == "gemma-3-27b-it"


def test_ollama_generate(monkeypatch):
    client = LLMClient(_settings(llm_provider="ollama"))
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp({"response": "  look up  "})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert client.generate("prompt") == "look up"
    assert captured["url"].endswith("/api/generate")
    assert captured["json"]["model"] == client.model


def test_openrouter_generate(monkeypatch):
    client = LLMClient(_settings(llm_provider="openrouter", openrouter_api_key="k"))
    payload = {"choices": [{"message": {"content": "hey there"}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(payload))
    assert client.generate("p") == "hey there"


def test_huggingface_generate(monkeypatch):
    client = LLMClient(_settings(llm_provider="huggingface", hf_api_key="k"))
    payload = {"choices": [{"message": {"content": "from hf"}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(payload))
    assert client.generate("p") == "from hf"


def test_google_generate(monkeypatch):
    client = LLMClient(_settings(llm_provider="google", google_api_key="k"))
    payload = {"candidates": [{"content": {"parts": [{"text": "gemma says hi"}]}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(payload))
    assert client.generate("p") == "gemma says hi"


def test_generate_returns_none_on_transport_error(monkeypatch):
    client = LLMClient(_settings(llm_provider="ollama"))

    def boom(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    assert client.generate("p") is None


def test_ollama_reachable(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp({}))
    assert _ollama_reachable("http://localhost:9") is True

    def boom(*args, **kwargs):
        raise httpx.ConnectError("x")

    monkeypatch.setattr(httpx, "get", boom)
    assert _ollama_reachable("http://localhost:9") is False
