# ✅ Submission checklist

A practical, tick-box guide for getting Horizon through the **Hacktoberfest
Open-Source AI Challenge (Week 1: Touch Grass)** and onto DEV.

> Deadline reference: the Week 1 window closes **Oct 11, 2026, 11:59 PM PDT**.
> Confirm the exact cut-off on the [challenge page](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).

## 1. Repository

- [ ] `git init` and push a public GitHub repo named `horizon`.
- [ ] Fill the placeholders (`<your-user>`) in `README.md` and
      `docs/DEV_SUBMISSION.md`.
- [ ] The repo shows the **MIT** license and a green CI badge.
- [ ] Add topics: `hacktoberfest`, `touch-grass`, `astronomy`, `fastapi`,
      `gemma`, `open-meteo`, `skyfield`, `python`.

## 2. Run it end-to-end (locally)

```bash
make dev            # install runtime + dev deps
make test           # 84+ tests, offline, ~1s
make lint           # ruff clean
make run            # http://localhost:8000
```

- [ ] One-button alert works with an **empty `.env`** (template narrator).
- [ ] Optional: `ollama pull gemma3:4b` then `LLM_PROVIDER=ollama` for Gemma.
- [ ] `python -m horizon.cli --city "Lisbon"` prints the alert.
- [ ] `GET /api/health` reports every partner as active/inactive correctly.

## 3. Deploy (pick at least one — they are prize categories)

- [ ] **Render**: *New +* → *Blueprint* → select `render.yaml`.
- [ ] **DigitalOcean**: `doctl apps create --spec .do/app.yaml`.
- [ ] Copy the live URL into `README.md` and `docs/DEV_SUBMISSION.md`.
- [ ] Set partner secrets in the host dashboard (they are marked secret in both
      specs) — never commit them.

## 4. Capture media

- [ ] Replace `docs/screenshot.svg` if the UI has changed (or export a PNG).
- [ ] Record a **short (20–40s) screen capture** of one tap → the alert.
      This *is* the "Touch Grass" story: short interaction, real-world payoff.
- [ ] Keep the video unlisted/embeddable (YouTube, Loom, or a GIF in the repo).

## 5. DEV submission post

Use `docs/DEV_SUBMISSION.md` as the draft. It already contains:

- [ ] **What I built** and **who it's for**.
- [ ] **Demo**: live link + screenshot + looped sample output.
- [ ] **How it works** (the stage table) and the open-source/weight story.
- [ ] **Prize Categories** with the exact category names.
- [ ] **The agent session** link (the prompt/session that built it).

Post tagline / frontmatter:

```
title: 🌇 Horizon — the best time to step outside, and what the sky has waiting
tags: hacktoberfest, devchallenge, hf26challenge, opensource, ai
```

- [ ] Add the required hashtags: `#hf26challenge` `#devchallenge`
      `#hacktoberfest` `#opensource` `#ai`.
- [ ] Cross-post the link back into the submission discussion thread.
- [ ] Double-check the post renders (images upload, code blocks fenced).

## 6. Final sanity pass

- [ ] `pytest` green on a clean checkout (CI enforces Python 3.10–3.12).
- [ ] No secrets in `git log` (`git grep -iE "sk-|api_key=|mongodb\+srv" $(git rev-list --all)`).
- [ ] `.cache/`, `.venv/`, `.env` are **not** committed (see `.gitignore`).
- [ ] Repo README opens with a screenshot a human can see in the first screen.
