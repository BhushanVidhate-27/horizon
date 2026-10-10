# Horizon container image.
# Partner categories: Best Use of DigitalOcean (App Platform) / Best Use of Render.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# System deps kept minimal; Skyfield is pure Python + NumPy.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Warm the ephemeris + geocode caches at build time so first request is fast.
RUN python -c "from horizon import sky; sky.SKYFIELD_AVAILABLE and sky._load_ephemeris()" || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -fsS http://localhost:${PORT}/api/health || exit 1

CMD ["sh", "-c", "uvicorn horizon.main:app --host 0.0.0.0 --port ${PORT}"]
