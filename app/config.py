"""Reads configuration from environment variables (see .env.example)."""
from __future__ import annotations

import os


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _parse_feeds(value: str) -> list[tuple[str, str]]:
    """Parse "Name|https://url,Name2|https://url2" into [(name, url), ...]."""
    feeds = []
    for entry in _split_csv(value):
        if "|" not in entry:
            continue
        name, url = entry.split("|", 1)
        feeds.append((name.strip(), url.strip()))
    return feeds


DEFAULT_FEEDS = (
    "BBC News|http://feeds.bbci.co.uk/news/rss.xml,"
    "BBC World|https://feeds.bbci.co.uk/news/world/rss.xml,"
    "Sky News|https://feeds.skynews.com/feeds/rss/home.xml,"
    "NPR|https://feeds.npr.org/1001/rss.xml"
)


class Config:
    # Comma-separated "Name|https://feed-url" pairs.
    RSS_FEEDS = _parse_feeds(os.environ.get("RSS_FEEDS", DEFAULT_FEEDS))

    # Headlines pulled from each feed, and the overall cap after
    # round-robin interleaving (the layout engine drops whatever doesn't
    # fit on the page, so this can comfortably be higher than what
    # actually renders).
    HEADLINES_PER_FEED = int(os.environ.get("HEADLINES_PER_FEED", "5"))
    TOTAL_HEADLINES = int(os.environ.get("TOTAL_HEADLINES", "18"))

    PAPER_NAME = os.environ.get("PAPER_NAME", "THE KINDLE TIMES")

    # "Now Reading" corner box: pulls the first book on this Goodreads
    # shelf (public profile, no API key needed) and shows its cover, title/
    # author, and average rating in the bottom-right corner of every
    # template. Leave GOODREADS_USER_ID empty to disable the feature
    # entirely -- the page just renders with no reserved space for it, same
    # as before this existed. ID can be the numeric id alone or the full
    # "id-slug" form from a profile URL (goodreads.com/user/show/<this>).
    GOODREADS_USER_ID = os.environ.get("GOODREADS_USER_ID", "70021579-richard-gwilt")
    GOODREADS_SHELF = os.environ.get("GOODREADS_SHELF", "currently-reading")

    # Times of day (24h HH:MM, in TZ below) at which to refresh the digest.
    UPDATE_TIMES = _split_csv(os.environ.get("UPDATE_TIMES", "07:00,13:00,19:00"))

    TZ = os.environ.get("TZ", "Europe/London")

    # Kindle Paperwhite (2024): 7", 1264x1680 px, 300 ppi, E Ink Carta 1300.
    KINDLE_WIDTH = int(os.environ.get("KINDLE_WIDTH", "1264"))
    KINDLE_HEIGHT = int(os.environ.get("KINDLE_HEIGHT", "1680"))

    DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
    CURRENT_IMAGE_PATH = os.path.join(DATA_DIR, "current.png")
    STATE_PATH = os.path.join(DATA_DIR, "state.json")

    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "8080"))

    # Refresh once on container startup, so /current.png isn't empty while
    # waiting for the first scheduled update time.
    FETCH_ON_STARTUP = os.environ.get("FETCH_ON_STARTUP", "true").lower() in ("1", "true", "yes")

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
