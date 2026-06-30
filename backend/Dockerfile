# ─── Stage 1: Base Python image ──────────────────────────────────────────────
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ─── Stage 2: Dependencies ───────────────────────────────────────────────────
FROM base AS deps

# Install build dependencies required by cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Stage 3: Production image ───────────────────────────────────────────────
FROM base AS production

# Create non-root user for security (never run as root in production)
RUN groupadd --gid 1001 cityapp && \
    useradd --uid 1001 --gid cityapp --shell /bin/bash --create-home cityapp

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application source
COPY --chown=cityapp:cityapp . .

# Keys directory — mounted at runtime, never baked into image
RUN mkdir -p /app/keys && chown cityapp:cityapp /app/keys

# Install curl for Docker healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

USER cityapp

EXPOSE 8000

# Uvicorn with multiple workers in production; single worker in development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
