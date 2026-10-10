"""Narrator tests: template fallback and LLM output parsing (offline)."""

from datetime import datetime, timezone

from horizon.models import (
    DailyAlert,
    Location,
    ProviderStatus,
    SkyEvent,
    SkyReport,
    WeatherWindow,
)
from horizon.narrator import (
    _build_prompt,
    _parse_llm_output,
    _template_message,
    _window_line,
    compose,
)


def _alert() -> DailyAlert:
    window = WeatherWindow(
        start=datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc),
        end=datetime(2026, 10, 10, 19, 0, tzinfo=timezone.utc),
        hours=2,
        score=87.0,
        summary="clear sky",
        temperature_c=24.0,
        feels_like_c=24.5,
        precipitation_probability=5,
        wind_kph=8.0,
        cloud_cover=10,
        uv_index=2.0,
    )
    return DailyAlert(
        location=Location(name="Test", latitude=0, longitude=0),
        generated_at=datetime.now(timezone.utc),
        generated_for_date="2026-10-10",
        headline="",
        message="",
        nudge="",
        weather_summary="Clear sky, 24°C.",
        best_window=window,
        sky_report=SkyReport(moon_phase_name="Waxing Crescent", moon_illumination=0.2),
        providers=ProviderStatus(),
    )


def test_template_compose_without_llm():
    alert = compose(_alert(), llm=None, use_llm=False)
    assert alert.headline
    assert "Best window" in alert.message
    assert "phone" in alert.nudge.lower()
    assert alert.providers.gemma is False


def test_parse_llm_labeled_output():
    text = (
        "HEADLINE: A perfect clear evening\n\n"
        "MESSAGE: Go out between 17:00 and 19:00. Clear skies and 24C.\n"
        "Look for the moon in the west.\n\n"
        "NUDGE: Pocket the phone and look up for two minutes."
    )
    headline, message, nudge = _parse_llm_output(text, _alert())
    assert headline == "A perfect clear evening"
    assert "17:00" in message
    assert "Pocket the phone" in nudge


class _FakeLLM:
    available = True
    provider = "ollama"

    def generate(self, prompt, system=None):
        return "HEADLINE: Go now\nMESSAGE: A lovely evening.\nNUDGE: Pocket the phone."


def test_compose_with_llm_marks_gemma_provider():
    alert = compose(_alert(), llm=_FakeLLM(), use_llm=True)
    assert alert.headline == "Go now"
    assert alert.providers.gemma is True
    assert alert.providers.llm_provider == "ollama"


def test_compose_records_template_when_llm_disabled():
    alert = compose(_alert(), llm=_FakeLLM(), use_llm=False)
    assert alert.providers.gemma is False
    assert alert.providers.llm_provider is None


def test_window_line_without_window():
    alert = _alert()
    alert.best_window = None
    assert "unavailable" in _window_line(alert)


def test_template_message_includes_news_and_events():
    alert = _alert()
    alert.sky_report.events = [SkyEvent(kind="moon", label="Full Moon", detail="Bright.")]
    alert.news = ["A comet is visible"]
    message = _template_message(alert)
    assert "Full Moon" in message
    assert "A comet is visible" in message


def test_build_prompt_contains_facts():
    prompt = _build_prompt(_alert())
    assert "WEATHER" in prompt
    assert "17:00-19:00" in prompt
    assert "HEADLINE" in prompt
