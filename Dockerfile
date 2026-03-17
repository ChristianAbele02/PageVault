# ── Build stage ────────────────────────────────────────────────────────────────
# Pin to a specific patch release for reproducible builds (issue #21)
FROM python:3.12.9-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENSE app.py ./
COPY pagevault_core/ pagevault_core/
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install ".[prod]"


# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.12.9-slim

LABEL org.opencontainers.image.title="PageVault"
LABEL org.opencontainers.image.description="Self-hosted personal book catalog with ISBN scanning"
LABEL org.opencontainers.image.source="https://github.com/ChristianAbele02/PageVault"
LABEL org.opencontainers.image.licenses="MIT"

# Non-root user for security
RUN groupadd -r pagevault && useradd -r -g pagevault pagevault

# Install curl for healthcheck (issue #20 — simpler and lower overhead than Python subprocess)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app.py .
COPY config.py .
COPY pagevault_core/ pagevault_core/
COPY templates/ templates/
COPY static/ static/

# Data directory (SQLite database lives here — mount as a volume)
# The path is configurable via PAGEVAULT_DB env var (issue #25)
RUN mkdir -p /data && chown pagevault:pagevault /data
ENV PAGEVAULT_DB=/data/pagevault.db

USER pagevault

EXPOSE 5000

# Simplified healthcheck using curl instead of a Python subprocess (issue #20)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:5000/api/stats > /dev/null

# Use gunicorn in production; 2 workers is plenty for a personal app
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:create_app()"]
