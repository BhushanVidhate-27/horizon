"""FastAPI endpoints (offline; the pipeline is stubbed)."""

import pytest
from fastapi.testclient import TestClient

import horizon.main as main
from horizon.models import Location


@pytest.fixture(autouse=True)
def _fresh_singletons():
    """Reset module-level singletons so each test uses its own cache/settings."""
    main._store = None
    main._llm = None
    yield
    main._store = None
    main._llm = None


@pytest.fixture
def client():
    return TestClient(main.app)


def test_index_serves_ui(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Horizon" in res.text


def test_health_reports_integrations(client):
    payload = client.get("/api/health").json()
    assert payload["status"] == "ok"
    assert payload["integrations"]["elevenlabs"] is False
    assert payload["storage"]["backend"] == "sqlite"


def test_geocode_ok(monkeypatch, client):
    monkeypatch.setattr(
        main, "geocode_city", lambda city: Location(name=city, latitude=1.0, longitude=2.0)
    )
    payload = client.get("/api/geocode?city=Lisbon").json()
    assert payload["name"] == "Lisbon"


def test_geocode_missing_returns_404(monkeypatch, client):
    monkeypatch.setattr(main, "geocode_city", lambda city: None)
    assert client.get("/api/geocode?city=Nowhereville").status_code == 404


def test_alert_get_and_post(monkeypatch, client, sample_alert):
    monkeypatch.setattr(main, "build_daily_alert", lambda request, **kwargs: sample_alert)

    got = client.get("/api/alert?city=Test")
    assert got.status_code == 200
    assert got.json()["headline"] == sample_alert.headline

    posted = client.post("/api/alert", json={"city": "Test", "speak": False})
    assert posted.status_code == 200
    assert posted.json()["location"]["name"] == "Test"


def test_history_and_stats(client):
    assert "alerts" in client.get("/api/history").json()
    assert client.get("/api/stats").json()["backend"] == "sqlite"


def test_search_searches_stored_alerts(client, sample_alert):
    main.store().save_alert(sample_alert)
    payload = client.get("/api/search?q=Best window").json()
    assert payload["query"] == "Best window"
    assert payload["results"][0]["headline"] == sample_alert.headline
    assert client.get("/api/search?q=nothing-matches").json()["results"] == []
