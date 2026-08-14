"""
Fetches the "currently reading" book from a public Goodreads shelf RSS feed,
for the small "Now Reading" corner feature on the front page -- a fluff
piece alongside the news, showing the cover, title/author, and the book's
average rating.

Goodreads' formal API was deprecated in 2020, but per-shelf RSS feeds
(https://www.goodreads.com/review/list_rss/<user_id>?shelf=<shelf>) are a
separate, older mechanism that has historically kept working for public
profiles independent of that API. If Goodreads ever retires this too, or
changes field names, fetching just fails gracefully like any other feed in
this project -- the corner box simply doesn't render that cycle.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import feedparser
import requests

log = logging.getLogger("frontpage.goodreads")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "kindle-frontpage-pusher/2.0"
)
REQUEST_TIMEOUT = 15  # seconds


@dataclass
class BookPick:
    title: str
    author: str
    rating: float | None  # the book's average Goodreads rating out of 5, if available
    cover_url: str | None
    link: str = ""


def _first_present(entry, *field_names):
    for name in field_names:
        val = getattr(entry, name, None)
        if val:
            return val
    return None


def fetch_currently_reading(user_id: str, shelf: str = "currently-reading") -> BookPick | None:
    """
    Returns a BookPick for the first (most recently updated) entry on the
    given shelf, or None if the shelf is empty, the feed can't be fetched,
    or nothing usable could be parsed out of it. Best-effort -- any failure
    here just means the corner box doesn't render this cycle, same fallback
    philosophy as everything else in this project.
    """
    if not user_id:
        return None

    url = f"https://www.goodreads.com/review/list_rss/{user_id}?shelf={shelf}"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            log.warning("Goodreads shelf fetch failed: HTTP %d for %s", resp.status_code, url)
            return None

        parsed = feedparser.parse(resp.content)
        if not parsed.entries:
            log.info("Goodreads shelf '%s' is empty (or feed failed to parse)", shelf)
            return None

        entry = parsed.entries[0]
        # Field names here are undocumented/legacy and could plausibly shift
        # -- log what's actually present so a mismatch is a quick fix rather
        # than a silent "no book ever shows up".
        log.debug("Goodreads entry fields: %s", sorted(entry.keys()))

        raw_title = (getattr(entry, "title", "") or "").strip()
        author = _first_present(entry, "author_name", "author")
        title = raw_title
        # This feed typically titles each item "Book Title by Author Name".
        if author and raw_title.endswith(f" by {author}"):
            title = raw_title[: -len(f" by {author}")].strip()
        elif not author and " by " in raw_title:
            title, _, author = raw_title.rpartition(" by ")
            title = title.strip()
            author = author.strip()

        if not title:
            log.warning("Goodreads entry had no usable title; fields were: %s", sorted(entry.keys()))
            return None

        cover_url = _first_present(
            entry,
            "book_large_image_url",
            "book_medium_image_url",
            "book_small_image_url",
            "book_image_url",
        )

        rating = None
        avg = _first_present(entry, "average_rating")
        if avg:
            try:
                rating = float(avg)
            except (TypeError, ValueError):
                rating = None

        link = getattr(entry, "link", "") or ""

        return BookPick(title=title, author=author or "", rating=rating, cover_url=cover_url, link=link)
    except Exception as e:  # noqa: BLE001 - any failure just means no corner box this cycle
        log.warning("Goodreads fetch failed: %s", e)
        return None
