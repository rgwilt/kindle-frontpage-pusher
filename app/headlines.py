"""
Fetches top headlines from a curated list of RSS feeds.

RSS is a much friendlier data source than scraping newspaper front-page
scans: feeds are built for exactly this kind of aggregation, there's no
anti-bot protection or cookie-consent dialogs to fight, and parsing is
well-standardized (via feedparser).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import feedparser
import requests

log = logging.getLogger("frontpage.headlines")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "kindle-frontpage-pusher/2.0"
)
REQUEST_TIMEOUT = 15  # seconds


@dataclass
class Headline:
    title: str
    source: str
    link: str


class FeedError(RuntimeError):
    """Raised when a single feed can't be fetched or parsed."""


def _fetch_one_feed(name: str, url: str, limit: int) -> list[Headline]:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        raise FeedError(f"{name}: HTTP {resp.status_code}")

    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        raise FeedError(f"{name}: unparseable feed ({parsed.bozo_exception})")
    if not parsed.entries:
        raise FeedError(f"{name}: feed had no entries")

    headlines = []
    for entry in parsed.entries[:limit]:
        title = getattr(entry, "title", None)
        link = getattr(entry, "link", "") or ""
        if not title:
            continue
        headlines.append(Headline(title=title.strip(), source=name, link=link))
    return headlines


def fetch_headlines(
    feeds: list[tuple[str, str]], per_feed: int, total: int
) -> tuple[list[Headline], list[str]]:
    """
    Fetch headlines from each (name, url) feed in `feeds`, up to `per_feed`
    per source, interleaved round-robin so no single source dominates, and
    capped at `total` overall.

    Returns (headlines, failed_feed_names). A feed failing doesn't abort the
    whole digest -- we just use whatever feeds did succeed, same fallback
    philosophy as the old newspaper-rotation logic.
    """
    per_source: list[list[Headline]] = []
    failed: list[str] = []

    for name, url in feeds:
        try:
            log.info("Fetching feed '%s': %s", name, url)
            headlines = _fetch_one_feed(name, url, per_feed)
            if headlines:
                per_source.append(headlines)
            else:
                failed.append(name)
        except FeedError as e:
            log.warning("Feed failed: %s", e)
            failed.append(name)
        except Exception as e:  # noqa: BLE001 - network/partownse oddities, don't abort the digest
            log.warning("Feed '%s' raised unexpectedly: %s", name, e)
            failed.append(name)

    # Round-robin interleave so headlines alternate by source rather than
    # being grouped source-by-source. Stops once every bucket is exhausted
    # (not just once `total` is hit) -- otherwise, whenever the combined
    # pool across all sources is smaller than `total`, `i` would keep
    # advancing past every bucket's length forever without `combined`
    # ever growing, looping indefinitely.
    combined: list[Headline] = []
    i = 0
    while len(combined) < total:
        added_this_round = False
        for bucket in per_source:
            if i < len(bucket):
                combined.append(bucket[i])
                added_this_round = True
                if len(combined) >= total:
                    break
        if not added_this_round:
            break
        i += 1

    return combined, failed
