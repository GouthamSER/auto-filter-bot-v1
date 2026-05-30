# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.10-slim

# ── System deps ───────────────────────────────────────────────────────────────
# gcc / libffi needed to compile TgCrypto & some motor/pymongo wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
# Copy requirements first so Docker can cache this layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy source ───────────────────────────────────────────────────────────────
COPY . .

# ── Heroku sets $PORT at runtime; default to 8080 for local runs ──────────────
ENV PORT=8080

# ── Entry point ───────────────────────────────────────────────────────────────
CMD ["python", "main.py"]
