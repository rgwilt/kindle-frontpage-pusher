# This base image ships a matching Python + Playwright + Chromium (and all
# its OS-level dependencies) pre-installed, which avoids the version
# mismatches / missing-library headaches of installing Playwright's browser
# on a generic slim image. Keep the tag's version in lockstep with the
# playwright== pin in requirements.txt.
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./

RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8080/healthz || exit 1

CMD ["python", "main.py"]
