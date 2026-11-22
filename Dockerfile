# syntax=docker/dockerfile:1
# CreatorOS container: dashboard + scheduler + Telegram bot in one process.
#
#   docker compose up -d            # recommended (see docker-compose.yml)
#   docker build -t creatoros .     # plain build
#   docker build --build-arg WITH_WHISPER=true -t creatoros:whisper .   # + local speech-to-text

# ---------- Stage 1: install Python dependencies into an isolated virtualenv ----------
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
ARG WITH_WHISPER=false
RUN pip install -r /tmp/requirements.txt \
 && if [ "$WITH_WHISPER" = "true" ]; then pip install faster-whisper; fi

# ---------- Stage 2: slim runtime image ----------
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="CreatorOS" \
      org.opencontainers.image.description="Open-source AI content studio: blogs, social posts, video and marketing" \
      org.opencontainers.image.source="https://github.com/aswinsamuel-codes/CreatorOS" \
      org.opencontainers.image.licenses="MIT"

# ffmpeg: video module · tzdata: correct local schedule times
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg tzdata \
 && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CREATOROS_HOST=0.0.0.0 \
    CREATOROS_PORT=8787 \
    CREATOROS_LOCAL_CONFIG=/app/data/config.local.yaml

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY creatoros ./creatoros
COPY config.yaml ./config.yaml
COPY profile ./profile
COPY workspace ./workspace

# Run as a non-root user; data, logs and workspace are volumes (see docker-compose.yml).
RUN useradd --create-home --uid 1000 creator \
 && mkdir -p data logs workspace/output workspace/media \
 && chown -R creator:creator /app
USER creator

EXPOSE 8787
VOLUME ["/app/data", "/app/workspace", "/app/profile", "/app/logs"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/status', timeout=4)" || exit 1

CMD ["python", "-m", "creatoros", "run", "--no-browser"]
