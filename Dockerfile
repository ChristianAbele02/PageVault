# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="PageVault"
LABEL org.opencontainers.image.description="Self-hosted personal book catalog with ISBN scanning"
LABEL org.opencontainers.image.source="https://github.com/ChristianAbele02/PageVault"
LABEL org.opencontainers.image.licenses="MIT"

# Non-root user for security
RUN groupadd -r pagevault && useradd -r -g pagevault pagevault

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app.py .
COPY pagevault_core/ pagevault_core/
COPY templates/ templates/
COPY static/ static/

# Data directory (SQLite database lives here — mount as a volume)
RUN mkdir -p /data && chown pagevault:pagevault /data
ENV PAGEVAULT_DB=/data/pagevault.db

# Install gunicorn for production
RUN pip install --no-cache-dir "gunicorn>=22.0"

USER pagevault

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/stats')"

# Use gunicorn in production; 2 workers is plenty for a personal app
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:create_app()"]
