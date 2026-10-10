# Security Policy

## Supported versions

Horizon is a small project; security fixes are applied to the latest `main`.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, use
GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities)
on this repository, or email the maintainer listed in the repository profile.
We aim to respond within a few days.

## Notes for self-hosters

Horizon is designed to run with **no API keys**. If you enable the optional
partners, keep their secrets out of version control:

- Use `.env` (git-ignored) or your platform's secret manager.
- The `.do/app.yaml` and `render.yaml` specs mark partner keys as secrets.
- Generated audio is written to `.cache/audio/` and served statically; treat the
  cache directory as ephemeral and do not commit it.
- Horizon never stores personally identifying data beyond a place name and the
  generated alert.
