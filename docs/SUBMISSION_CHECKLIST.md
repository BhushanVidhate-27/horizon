# ✅ Submission checklist

A practical, tick-box guide for getting Horizon through the **Hacktoberfest
Open-Source AI Challenge (Week 1: Touch Grass)** and onto DEV.

> Deadline reference: the Week 1 window closes **Oct 11, 2026, 11:59 PM PDT**.
> Confirm the exact cut-off on the [challenge page](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).

## 1. Repository

- [x] `git init` and push a public GitHub repo named `horizon` (owner:
      `bhushanvidhate-27` — already set as `bhushanvidhate-27/horizon` in
      every badge, link and spec).
- [ ] **Verify the live URL once Render deploys**: the demo links currently say
      `https://horizon-bhushanvidhate-27.onrender.com` — replace that subdomain
      with the exact one Render assigns in `README.md` and
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

- [x] **Render**: *New +* → *Blueprint* → select `render.yaml` *(this is the
      live demo)*.
- [ ] **DigitalOcean** *(optional, easiest $200 category this week — only
      ~2 rivals)*: `doctl apps create --spec .do/app.yaml`, then point the
      live demo there instead.
- [ ] Copy the live URL into `README.md` and `docs/DEV_SUBMISSION.md`.
- [ ] Set partner secrets in the host dashboard (they are marked secret in both
      specs) — never commit them.

## 4. Capture media

- [ ] The screenshot for DEV is already exported at **`docs/screenshot.png`**
      (1200px wide). To regenerate: `qlmanage -t -s 1600 -o /tmp docs/screenshot.svg
      && mv /tmp/screenshot.svg.png docs/screenshot.png`. Upload it into the post
      (DEV can't upload SVG).
- [ ] Record a **short (20–40s) screen capture** of one tap → the alert.
      This *is* the "Touch Grass" story: short interaction, real-world payoff.
- [ ] Keep the video unlisted/embeddable (YouTube, Loom, or a GIF in the repo).

## 5. DEV submission post

Use `docs/DEV_SUBMISSION.md` as the draft. It already contains every
**template section** in order:

- [ ] **What I Built** and **Who It's For**.
- [ ] **Demo**: live link + screenshot + looped sample output.
- [ ] **Code**: embedded GitHub repo + quick repo tour.
- [ ] **How I Built It** (the stage table) and the open-source/weight story.
- [ ] **Why Does Open Innovation Matter?**
- [ ] **My Agent Session**: save the build session to DEV with
      [DevRelay](https://devrelay.com) and replace `YOUR_SESSION_ID_OR_SLUG` in
      `{% agent_session ... %}` (or delete the line to skip it).
- [ ] **Prize Categories** with the exact category names.

Frontmatter (already at the top of the draft):

```
title: 🌇 Horizon — the best time to step outside, and what the sky has waiting
published: false
tags: devchallenge, hf26challenge, opensource, ai
```

- [ ] Required hashtags are present in the body: `#hf26challenge`
      `#devchallenge` (`#opensource` `#ai` as bonus).
- [ ] Set `published: true` (before the deadline) and verify the post renders —
      images must upload, GitHub embed must show the repo card.
- [ ] Cross-post the link back into the submission discussion thread.

## 6. Final sanity pass

- [ ] `pytest` green on a clean checkout (CI enforces Python 3.10–3.12).
- [ ] No secrets in `git log` (`git grep -iE "sk-|api_key=|mongodb\+srv" $(git rev-list --all)`).
- [ ] `.cache/`, `.venv/`, `.env` are **not** committed (see `.gitignore`).
- [ ] Repo README opens with a screenshot a human can see in the first screen.
- [ ] Post-deadline commits (if any) noted at the top of the README as required
      by the [rules](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).