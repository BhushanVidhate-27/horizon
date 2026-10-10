"""CLI rendering and argument wiring (offline)."""

import json

from horizon import cli


def test_render_includes_all_sections(sample_alert):
    out = cli._render(sample_alert)
    assert "HORIZON" in out
    assert sample_alert.headline in out
    assert "Best window" in out
    assert "17:00 - 19:00" in out
    assert sample_alert.nudge in out
    assert "Providers" in out


def test_main_json(monkeypatch, capsys, sample_alert):
    monkeypatch.setattr(cli, "build_daily_alert", lambda request, **kwargs: sample_alert)
    assert cli.main(["--city", "Test", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["headline"] == sample_alert.headline


def test_main_text(monkeypatch, capsys, sample_alert):
    monkeypatch.setattr(cli, "build_daily_alert", lambda request, **kwargs: sample_alert)
    assert cli.main(["--city", "Test"]) == 0
    assert "HORIZON" in capsys.readouterr().out


def test_request_flags_are_forwarded(monkeypatch, sample_alert):
    captured = {}

    def fake_build(request, **kwargs):
        captured["request"] = request
        return sample_alert

    monkeypatch.setattr(cli, "build_daily_alert", fake_build)
    cli.main(["--lat", "48.85", "--lon", "2.35", "--no-llm", "--speak"])

    request = captured["request"]
    assert request.latitude == 48.85 and request.longitude == 2.35
    assert request.use_llm is False
    assert request.speak is True
