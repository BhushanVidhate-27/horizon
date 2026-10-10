"""Command-line interface for Horizon.

Examples:
    python -m horizon.cli --city "Tokyo"
    python -m horizon.cli --lat 48.85 --lon 2.35 --speak
    python -m horizon.cli --city Pune --json
"""

from __future__ import annotations

import argparse
import sys

from .agent import build_daily_alert
from .models import AlertRequest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="horizon", description="Daily outside alert & sky planner"
    )
    parser.add_argument("--city", help="City name, e.g. 'Lisbon'")
    parser.add_argument("--lat", type=float, help="Latitude")
    parser.add_argument("--lon", type=float, help="Longitude")
    parser.add_argument("--speak", action="store_true", help="Generate ElevenLabs audio")
    parser.add_argument(
        "--no-llm", action="store_true", help="Skip Gemma; use the template narrator"
    )
    parser.add_argument("--json", action="store_true", help="Print the raw JSON alert")
    return parser


def _render(alert) -> str:
    window = alert.best_window
    loc = alert.location
    lines = []
    lines.append("=" * 62)
    lines.append(f"  HORIZON  ·  {loc.display_name or loc.name}")
    lines.append("=" * 62)
    meta_bits = [f"{loc.latitude:.3f}, {loc.longitude:.3f}"]
    if loc.elevation is not None:
        meta_bits.append(f"{loc.elevation:.0f} m")
    if loc.timezone:
        meta_bits.append(loc.timezone)
    if loc.feature_code:
        meta_bits.append(loc.feature_code)
    lines.append("  " + "  ·  ".join(meta_bits))
    lines.append("")
    lines.append(alert.headline)
    lines.append("")
    if window:
        lines.append(
            f"Best window : {window.start.strftime('%H:%M')} - {window.end.strftime('%H:%M')} "
            f"(score {window.score:.0f}/100)"
        )
    lines.append(f"Weather     : {alert.weather_summary}")
    lines.append("")

    sky = alert.sky_report
    if sky.sunrise and sky.sunset:
        lines.append(
            f"Sun         : up {sky.sunrise.strftime('%H:%M')} / down {sky.sunset.strftime('%H:%M')}"
        )
    lines.append(f"Moon        : {sky.moon_phase_name} ({int(sky.moon_illumination * 100)}% lit)")

    visible = [p for p in sky.planets if p.visible]
    if visible:
        lines.append("Planets     : " + ", ".join(f"{p.name} ({p.direction})" for p in visible))
    if sky.constellations:
        lines.append("Look up for : " + ", ".join(c.name for c in sky.constellations))
    if sky.meteor_showers:
        lines.append(
            "Meteors     : "
            + ", ".join(
                f"{m.name} ({'peak' if m.near_peak else 'active'})" for m in sky.meteor_showers
            )
        )
    lines.append("")
    lines.append("-" * 62)
    lines.append(alert.message)
    lines.append("")
    lines.append(alert.nudge)
    lines.append("")
    if alert.audio_url:
        lines.append(f"Audio       : {alert.audio_url}")
    providers = alert.providers
    lines.append(
        "Providers   : "
        + ", ".join(
            filter(
                None,
                [
                    f"Gemma({providers.llm_provider})" if providers.gemma else None,
                    "ElevenLabs" if providers.elevenlabs else None,
                    "MongoDB" if providers.mongodb else None,
                    "SerpApi" if providers.serpapi else None,
                    "Sentry" if providers.sentry else None,
                    f"host={providers.hosting}",
                ],
            )
        )
    )
    lines.append("=" * 62)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    request = AlertRequest(
        city=args.city,
        latitude=args.lat,
        longitude=args.lon,
        speak=args.speak,
        use_llm=not args.no_llm,
    )
    alert = build_daily_alert(request)

    if args.json:
        print(alert.model_dump_json(indent=2))
    else:
        print(_render(alert))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
