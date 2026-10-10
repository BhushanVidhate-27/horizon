"""Narrator: turns structured facts into the human daily alert.

Two paths:
  1. **Gemma** (via :mod:`horizon.llm`) writes the headline, message and nudge.
  2. A deterministic, friendly template writes them when no LLM is available.

Both paths consume the same :class:`~horizon.models.DailyAlert`, so the rest of
the app does not care which one ran.
"""

from __future__ import annotations

from .llm import LLMClient
from .models import DailyAlert


def _window_line(alert: DailyAlert) -> str:
    window = alert.best_window
    if not window:
        return "Weather data was unavailable, but the sky still has things to show you."
    return (
        f"Best window: {window.start.strftime('%H:%M')}-{window.end.strftime('%H:%M')} "
        f"({window.summary}, {window.temperature_c:.0f}°C, "
        f"{window.precipitation_probability}% rain chance, score {window.score:.0f}/100)."
    )


def _template_message(alert: DailyAlert) -> str:
    lines: list[str] = []
    lines.append(_window_line(alert))

    highlights = [e for e in alert.sky_report.events if e.kind != "news"][:4]
    if highlights:
        lines.append("Look up for:")
        for event in highlights:
            lines.append(f"  • {event.label} — {event.detail}")

    if alert.news:
        lines.append("Sky in the news:")
        for headline in alert.news[:2]:
            lines.append(f"  • {headline}")

    return "\n".join(lines)


def _template_nudge(alert: DailyAlert) -> str:
    window = alert.best_window
    when = window.start.strftime("%H:%M") if window else "today"
    return (
        f"Put the phone in your pocket at {when}, step outside, and give the sky "
        "two unhurried minutes. No filters needed."
    )


def _build_prompt(alert: DailyAlert) -> str:
    window = alert.best_window
    window_txt = "unavailable"
    if window:
        window_txt = (
            f"{window.start.strftime('%H:%M')}-{window.end.strftime('%H:%M')} "
            f"({window.summary}, {window.temperature_c:.0f}C, "
            f"{window.precipitation_probability}% rain, {window.wind_kph:.0f} km/h wind, "
            f"{window.cloud_cover}% cloud, UV {window.uv_index:.0f})"
        )

    sky = alert.sky_report
    planet_txt = (
        ", ".join(
            f"{p.name} {p.direction} {p.altitude_deg:.0f}deg" for p in sky.planets if p.visible
        )
        or "none obvious"
    )
    constellation_txt = ", ".join(f"{c.name} ({c.direction})" for c in sky.constellations) or "none"
    meteor_txt = (
        ", ".join(f"{m.name} near peak" for m in sky.meteor_showers if m.near_peak) or "none"
    )
    news_txt = "; ".join(alert.news) or "none"

    return f"""
Write today's Horizon alert for {alert.location.name}.

WEATHER
- Best outdoor window: {window_txt}

SKY
- Sunrise: {sky.sunrise.strftime("%H:%M") if sky.sunrise else "n/a"}
- Sunset: {sky.sunset.strftime("%H:%M") if sky.sunset else "n/a"}
- Moon: {sky.moon_phase_name} ({int(sky.moon_illumination * 100)}% lit)
- Visible planets: {planet_txt}
- Constellations high up: {constellation_txt}
- Meteor showers near peak: {meteor_txt}
- Sky news: {news_txt}

Write 3 short sections separated by blank lines:
1) HEADLINE: one inviting sentence (max 12 words).
2) MESSAGE: 2-4 sentences with the best window, the weather, and 2-4 sky things to look for.
3) NUDGE: one sentence telling the reader to put the phone away and go outside.
Keep it warm and concrete. Do not use emojis.
""".strip()


def compose(alert: DailyAlert, llm: LLMClient | None = None, use_llm: bool = True) -> DailyAlert:
    """Fill in headline/message/nudge on the alert (LLM when available)."""
    llm = llm or LLMClient()

    if use_llm and llm.available:
        text = llm.generate(_build_prompt(alert))
        if text:
            headline, message, nudge = _parse_llm_output(text, alert)
            alert.headline = headline
            alert.message = message
            alert.nudge = nudge
            alert.providers.gemma = True
            alert.providers.llm_provider = llm.provider
            return alert

    # Deterministic fallback.
    alert.headline = _template_headline(alert)
    alert.message = _template_message(alert)
    alert.nudge = _template_nudge(alert)
    alert.providers.gemma = False
    alert.providers.llm_provider = None
    return alert


def _template_headline(alert: DailyAlert) -> str:
    window = alert.best_window
    if window:
        return f"Your best outside window is {window.start.strftime('%H:%M')}-{window.end.strftime('%H:%M')}"
    return "A quiet sky is still worth a look today"


def _parse_llm_output(text: str, alert: DailyAlert) -> tuple[str, str, str]:
    """Best-effort parse of the three labelled sections."""
    headline = _template_headline(alert)
    message = _template_message(alert)
    nudge = _template_nudge(alert)

    lines = [ln.strip() for ln in text.splitlines()]
    current: str | None = None
    buckets: dict[str, list[str]] = {"headline": [], "message": [], "nudge": []}

    for line in lines:
        upper = line.upper()
        if upper.startswith("HEADLINE"):
            current = "headline"
            remainder = line.split(":", 1)[1].strip() if ":" in line else ""
            if remainder:
                buckets["headline"].append(remainder)
            continue
        if upper.startswith("MESSAGE"):
            current = "message"
            remainder = line.split(":", 1)[1].strip() if ":" in line else ""
            if remainder:
                buckets["message"].append(remainder)
            continue
        if upper.startswith("NUDGE"):
            current = "nudge"
            remainder = line.split(":", 1)[1].strip() if ":" in line else ""
            if remainder:
                buckets["nudge"].append(remainder)
            continue
        if current and line:
            buckets[current].append(line)

    if buckets["headline"]:
        headline = " ".join(buckets["headline"]).strip()
    if buckets["message"]:
        message = "\n".join(buckets["message"]).strip()
    if buckets["nudge"]:
        nudge = " ".join(buckets["nudge"]).strip()
    return headline, message, nudge
