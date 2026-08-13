"""Reads configuration from environment variables (see .env.example)."""
from __future__ import annotations

import os


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


class Config:
    # Newspapers to rotate through, one at a time. Slugs come from the
    # newspaper's URL on frontpages.com, e.g. https://www.frontpages.com/the-new-york-times/
    # -> "the-new-york-times"
    NEWSPAPERS = _split_csv(
        os.environ.get(
            "NEWSPAPERS",
            "the-new-york-times,the-washington-post,usa-today,financial-times,"
            "the-herald-scotland,the-irish-times,new-york-post,chicago-tribune",
        )
    )

    # Times of day (24h HH:MM, in TZ below) at which to advance the rotation
    # and push a fresh image.
    UPDATE_TIMES = _split_csv(os.environ.get("UPDATE_TIMES", "07:00,13:00,19:00"))

    TZ = os.environ.get("TZ", "Europe/London")

    # Kindle Paperwhite (2024): 7", 1264x1680 px, 300 ppi, E Ink Carta 1300.
    KINDLE_WIDTH = int(os.environ.get("KINDLE_WIDTH", "1264"))
    KINDLE_HEIGHT = int(os.environ.get("KINDLE_HEIGHT", "1680"))

    IMAGE_FIT = os.environ.get("IMAGE_FIT", "contain")  # "contain" or "cover"
    BACKGROUND = os.environ.get("BACKGROUND", "white")  # "white" or "black"
    CONTRAST = float(os.environ.get("CONTRAST", "1.15"))
    SHARPEN = os.environ.get("SHARPEN", "true").lower() in ("1", "true", "yes")

    DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
    CURRENT_IMAGE_PATH = os.path.join(DATA_DIR, "current.png")
    STATE_PATH = os.path.join(DATA_DIR, "state.json")

    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "8080"))

    # How many papers to try (in rotation order) in a single update cycle
    # before giving up, if a given newspaper's page/image can't be fetched.
    MAX_ATTEMPTS_PER_CYCLE = int(os.environ.get("MAX_ATTEMPTS_PER_CYCLE", "3"))

    # Refresh the current.png once on container startup, so /current.png
    # isn't empty while waiting for the first scheduled update time.
    FETCH_ON_STARTUP = os.environ.get("FETCH_ON_STARTUP", "true").lower() in ("1", "true", "yes")

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
