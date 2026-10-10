"""Configuration defaults, feature flags and caching (offline)."""

from horizon.config import Settings, get_settings


def _settings(**overrides) -> Settings:
    # Ignore any local ``.env`` and the test env so assertions are deterministic.
    base = {"llm_provider": "auto"}
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_partner_flags_default_off():
    s = _settings()
    assert s.has_elevenlabs is False
    assert s.has_serpapi is False
    assert s.has_mongodb is False
    assert s.has_sentry is False
    assert s.has_llm is True


def test_partner_flags_turn_on_with_keys():
    s = _settings(
        elevenlabs_api_key="e",
        serpapi_api_key="s",
        mongodb_uri="mongodb://x",
        sentry_dsn="https://x",
    )
    assert s.has_elevenlabs and s.has_serpapi and s.has_mongodb and s.has_sentry


def test_has_llm_respects_none_provider():
    assert _settings(llm_provider="none").has_llm is False
    assert _settings(llm_provider="NONE").has_llm is False
    assert _settings(llm_provider="ollama").has_llm is True


def test_default_location_is_hyderabad():
    s = _settings()
    assert s.default_location_name == "Hyderabad, India"
    assert s.default_latitude == 17.3850


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
