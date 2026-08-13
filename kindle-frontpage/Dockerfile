FROM python:3.11-slim

# tzdata lets Python's zoneinfo resolve TZ names like "Europe/London" for
# the scheduler; curl is only used by the HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata curl \
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
