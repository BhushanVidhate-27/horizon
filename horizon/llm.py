"""Gemma / open-weight LLM narration.

Turns the raw weather + sky facts into a warm, human daily alert. Supports:

  * ``ollama``        -> local Gemma (fully open, no key, no cost)
  * ``openrouter``    -> hosted Gemma via OpenRouter
  * ``google``        -> Google AI Studio (Gemma models)
  * ``huggingface``   -> HF Inference router (Gemma models)

If nothing is configured (or every call fails) ``generate()`` returns ``None``
and the caller falls back to the deterministic template narrator, so the core
app never depends on a paid API.
"""

from __future__ import annotations

import logging

import httpx

from .config import Settings, get_settings

log = logging.getLogger("horizon.llm")

SYSTEM_PROMPT = (
    "You are Horizon, a friendly companion that helps people step outside and "
    "look up at the sky. You write short, warm, concrete daily alerts. Use plain "
    "language, no marketing fluff, no emojis unless asked. Always mention the "
    "best time window, the weather at a glance, and 2-4 sky things to look for. "
    "End with one gentle nudge to put the phone away and go outside."
)


class LLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.provider = self._pick_provider()
        self.model = self._pick_model()

    # -- provider selection ------------------------------------------------
    def _pick_provider(self) -> str:
        requested = self.settings.llm_provider.lower()
        if requested != "auto":
            return requested
        # Prefer free/local first, then whatever key is available.
        if _ollama_reachable(self.settings.ollama_base_url):
            return "ollama"
        if self.settings.openrouter_api_key:
            return "openrouter"
        if self.settings.google_api_key:
            return "google"
        if self.settings.hf_api_key:
            return "huggingface"
        return "none"

    def _pick_model(self) -> str | None:
        return {
            "ollama": self.settings.ollama_model,
            "openrouter": self.settings.openrouter_model,
            "google": self.settings.google_model,
            "huggingface": self.settings.hf_model,
        }.get(self.provider)

    @property
    def available(self) -> bool:
        return self.provider != "none"

    # -- public API --------------------------------------------------------
    def generate(self, prompt: str, system: str = SYSTEM_PROMPT) -> str | None:
        if not self.available:
            return None
        try:
            if self.provider == "ollama":
                return self._ollama(prompt, system)
            if self.provider == "openrouter":
                return self._openai_compatible(
                    "https://openrouter.ai/api/v1/chat/completions",
                    self.settings.openrouter_api_key,
                    prompt,
                    system,
                )
            if self.provider == "huggingface":
                return self._openai_compatible(
                    "https://router.huggingface.co/v1/chat/completions",
                    self.settings.hf_api_key,
                    prompt,
                    system,
                )
            if self.provider == "google":
                return self._google(prompt, system)
        except Exception as exc:
            log.warning("LLM generation failed via %s: %s", self.provider, exc)
        return None

    # -- provider implementations -----------------------------------------
    def _ollama(self, prompt: str, system: str) -> str | None:
        resp = httpx.post(
            f"{self.settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.7},
            },
            timeout=self.settings.llm_timeout,
        )
        resp.raise_for_status()
        return (resp.json().get("response") or "").strip() or None

    def _openai_compatible(
        self, url: str, api_key: str | None, prompt: str, system: str
    ) -> str | None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = httpx.post(
            url,
            headers=headers,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
            },
            timeout=self.settings.llm_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip() or None

    def _google(self, prompt: str, system: str) -> str | None:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        resp = httpx.post(
            url,
            params={"key": self.settings.google_api_key},
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7},
            },
            timeout=self.settings.llm_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip() or None


def _ollama_reachable(base_url: str) -> bool:
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=1.5)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False
