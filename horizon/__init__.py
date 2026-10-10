"""Horizon — daily outside alert & sky event planner.

A lightweight "Touch Grass" companion: it finds the best outdoor window of your
day, computes the sky events visible from where you are, and turns that into a
short, friendly daily nudge to put the phone away and go look up.

Hacktoberfest 2026 — Week 1: "Touch Grass" submission.

Partner technology categories this project enters:
  * Best Use of Gemma            -> horizon/llm.py   (daily alert narration)
  * Best Use of ElevenLabs       -> horizon/voice.py (spoken alert)
  * Best Use of DigitalOcean /
    Best Use of Render           -> Dockerfile / render.yaml (hosting)
  * Best Use of MongoDB Atlas    -> horizon/storage.py (location prefs + alert history)
  * Best Use of SerpApi          -> horizon/news.py  (rare sky-event news)
  * Best Use of Sentry           -> horizon/agent.py (agent tracing)
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
