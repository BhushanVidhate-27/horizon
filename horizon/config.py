"""Central configuration.

Everything is optional: Horizon is designed so the core experience (weather +
sky events + a template-based daily alert) works with **zero** API keys. Each
partner integration activates automatically when its key/URL is present.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Horizon"
    app_version: str = "0.1.0"
    debug: bool = False

    # --- Location / cache -------------------------------------------------
    cache_dir: str = ".cache"
    request_timeout: float = 20.0
    # Reverse-geocode GPS coordinates to a real place name (village / suburb).
    # Uses free, key-less services (OpenStreetMap Nominatim + BigDataCloud).
    reverse_geocode_enabled: bool = True
    # Default location used when the user supplies nothing (Hyderabad, IN).
    default_latitude: float = 17.3850
    default_longitude: float = 78.4867
    default_location_name: str = "Hyderabad, India"

    # --- Gemma / open-weight LLM -----------------------------------------
    # llm_provider: auto | ollama | openrouter | google | huggingface | none
    llm_provider: str = "auto"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemma-3-27b-it"
    google_api_key: str | None = None
    google_model: str = "gemma-3-27b-it"
    hf_api_key: str | None = None
    hf_model: str = "google/gemma-3-27b-it"
    llm_timeout: float = 60.0

    # --- ElevenLabs -------------------------------------------------------
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model: str = "eleven_multilingual_v2"

    # --- SerpApi ----------------------------------------------------------
    serpapi_api_key: str | None = None

    # --- MongoDB Atlas ----------------------------------------------------
    mongodb_uri: str | None = None
    mongodb_db: str = "horizon"

    # --- Sentry -----------------------------------------------------------
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.2
    sentry_environment: str = "development"

    @property
    def has_llm(self) -> bool:
        """True unless LLM narration has been explicitly disabled."""
        return self.llm_provider.lower() != "none"

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key)

    @property
    def has_serpapi(self) -> bool:
        return bool(self.serpapi_api_key)

    @property
    def has_mongodb(self) -> bool:
        return bool(self.mongodb_uri)

    @property
    def has_sentry(self) -> bool:
        return bool(self.sentry_dsn)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
