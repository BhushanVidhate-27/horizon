"""Agent orchestration (offline; every pipeline stage is stubbed)."""

from datetime import datetime, timezone

import pytest

from horizon import agent
from horizon.models import AlertRequest, HourlyPoint, Location, SkyEvent, SkyReport, WeatherWindow

LOC = Location(
    name="Testville",
    latitude=17.385,
    longitude=78.4867,
    timezone="Asia/Kolkata",
    display_name="Testville, India",
)


@pytest.fixture
def stub_pipeline(monkeypatch):
    window = WeatherWindow(
        start=datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc),
        end=datetime(2026, 10, 10, 19, 0, tzinfo=timezone.utc),
        hours=2,
        score=88.0,
        summary="clear sky",
        temperature_c=27.0,
        feels_like_c=27.0,
        precipitation_probability=5,
        wind_kph=8.0,
        cloud_cover=12,
        uv_index=2.0,
    )
    points = [
        HourlyPoint(
            time=datetime(2026, 10, 10, h, 0, tzinfo=timezone.utc),
            score=80.0,
            temperature_c=27.0,
            precipitation_probability=5,
            cloud_cover=12,
        )
        for h in range(24)
    ]
    monkeypatch.setattr(agent, "resolve_location", lambda *a, **k: LOC)
    monkeypatch.setattr(
        agent.sky_mod,
        "compute_sky_report",
        lambda location, date=None: SkyReport(
            sunrise=datetime(2026, 10, 10, 6, 6, tzinfo=timezone.utc),
            sunset=datetime(2026, 10, 10, 17, 52, tzinfo=timezone.utc),
            moon_phase_name="Waxing Crescent",
            moon_illumination=0.24,
            events=[SkyEvent(kind="moon", label="Waxing Crescent", detail="Look up.")],
        ),
    )
    monkeypatch.setattr(
        agent.weather, "get_weather", lambda location, daylight=None: (window, points)
    )
    monkeypatch.setattr(agent.news, "fetch_sky_news", lambda *a, **k: [])
    return window, points


def test_build_daily_alert_offline(stub_pipeline):
    alert = agent.build_daily_alert(AlertRequest(city="Testville"))

    assert alert.location.name == "Testville"
    assert alert.best_window is not None
    assert alert.best_window.score == 88.0
    assert len(alert.hourly) == 24
    assert alert.headline and alert.message and alert.nudge
    assert "Waxing Crescent" in alert.message
    assert alert.providers.gemma is False
    assert alert.providers.mongodb is False
    assert alert.providers.serpapi is False


def test_news_becomes_events_and_flag(stub_pipeline, monkeypatch):
    monkeypatch.setattr(agent.news, "fetch_sky_news", lambda *a, **k: ["Comet spotted over Europe"])
    alert = agent.build_daily_alert(AlertRequest(city="Testville"))

    assert alert.news == ["Comet spotted over Europe"]
    assert alert.providers.serpapi is True
    assert any(e.kind == "news" for e in alert.sky_report.events)


def test_speak_sets_audio_url(stub_pipeline, monkeypatch):
    monkeypatch.setattr(agent.voice, "synthesize", lambda text: "/audio/abc.mp3")
    alert = agent.build_daily_alert(AlertRequest(city="Testville", speak=True))

    assert alert.audio_url == "/audio/abc.mp3"
    assert alert.providers.elevenlabs is True


def test_speak_without_voice_leaves_audio_empty(stub_pipeline):
    # ELEVENLABS_API_KEY is unset in tests, so synthesize() returns None.
    alert = agent.build_daily_alert(AlertRequest(city="Testville", speak=True))
    assert alert.audio_url is None
    assert alert.providers.elevenlabs is False


def test_storage_failure_is_swallowed(stub_pipeline, monkeypatch):
    def boom(self, alert):
        raise RuntimeError("db down")

    monkeypatch.setattr(agent.Storage, "save_alert", boom)
    # The alert is still returned even though persistence blew up.
    assert agent.build_daily_alert(AlertRequest(city="Testville")).headline


def test_weather_summary_handles_missing_window():
    assert "unavailable" in agent._weather_summary(None).lower()


def test_location_tz_falls_back_to_utc():
    tz = agent.location_tz(Location(name="X", latitude=0, longitude=0, timezone="Not/AZone"))
    assert getattr(tz, "key", str(tz)) == "UTC"
