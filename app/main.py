from __future__ import annotations

import logging
import sys

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from waitress import serve

from config import Config
from goodreads import fetch_currently_reading
from headlines import fetch_headlines
from layout import render_digest
from server import build_app
from state import State

logging.basicConfig(
    level=Config.LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("frontpage.main")

state = State(Config.STATE_PATH)


def run_update_cycle() -> None:
    """Fetch headlines from all configured feeds and render a fresh digest.

    If some feeds fail, we still render from whatever succeeded (same
    fallback philosophy as before: partial data beats no update). Only if
    every single feed fails do we leave the previous image in place.
    """
    feeds = Config.RSS_FEEDS
    if not feeds:
        log.error("RSS_FEEDS is empty; nothing to fetch")
        return

    state.record_attempt()

    try:
        headlines, failed = fetch_headlines(
            feeds, per_feed=Config.HEADLINES_PER_FEED, total=Config.TOTAL_HEADLINES
        )
    except Exception as e:  # noqa: BLE001 - genuinely unexpected, log and bail
        log.exception("Unexpected error fetching headlines")
        state.record_error(str(e))
        return

    if not headlines:
        msg = f"All {len(feeds)} feed(s) failed: {', '.join(failed) or 'unknown'}"
        log.error(msg)
        state.record_error(msg)
        return

    # Best-effort "Now Reading" corner box -- a failure here (Goodreads down,
    # shelf empty, feed format changed) should never take down the whole
    # digest, so it's fetched separately from the headlines and defaults to
    # None (meaning: don't reserve any space for it) on any problem.
    book = None
    if Config.GOODREADS_USER_ID:
        try:
            book = fetch_currently_reading(Config.GOODREADS_USER_ID, shelf=Config.GOODREADS_SHELF)
        except Exception as e:  # noqa: BLE001 - never let this abort the digest
            log.warning("Unexpected error fetching Goodreads shelf: %s", e)
            book = None

    try:
        png_bytes, used = render_digest(
            headlines,
            width=Config.KINDLE_WIDTH,
            height=Config.KINDLE_HEIGHT,
            paper_name=Config.PAPER_NAME,
            book=book,
        )
        with open(Config.CURRENT_IMAGE_PATH, "wb") as f:
            f.write(png_bytes)
    except Exception as e:  # noqa: BLE001 - rendering shouldn't normally fail, but don't crash the loop
        log.exception("Unexpected error rendering digest")
        state.record_error(str(e))
        return

    sources_used = sorted({h.source for h in headlines[:used]})
    now_reading = f"{book.title} by {book.author}" if book and book.author else (book.title if book else None)
    state.record_success(
        headlines_used=used, sources_used=sources_used, failed_feeds=failed, now_reading=now_reading
    )
    log.info(
        "Update cycle succeeded: %d headline(s) from %s%s%s",
        used,
        ", ".join(sources_used),
        f" (failed: {', '.join(failed)})" if failed else "",
        f"; now reading: {now_reading}" if now_reading else "",
    )


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=Config.TZ)
    for time_str in Config.UPDATE_TIMES:
        try:
            hour, minute = time_str.split(":")
        except ValueError:
            log.warning("Ignoring malformed UPDATE_TIMES entry: %r", time_str)
            continue
        scheduler.add_job(
            run_update_cycle,
            CronTrigger(hour=int(hour), minute=int(minute), timezone=Config.TZ),
            id=f"update-{time_str}",
            misfire_grace_time=3600,
        )
        log.info("Scheduled update at %s %s", time_str, Config.TZ)
    scheduler.start()
    return scheduler


def main() -> None:
    log.info(
        "Starting kindle-frontpage-pusher: %d feed(s), %dx%d target, updates at %s (%s), "
        "Goodreads corner box %s",
        len(Config.RSS_FEEDS), Config.KINDLE_WIDTH, Config.KINDLE_HEIGHT,
        ", ".join(Config.UPDATE_TIMES), Config.TZ,
        f"enabled ({Config.GOODREADS_USER_ID}, shelf={Config.GOODREADS_SHELF})" if Config.GOODREADS_USER_ID else "disabled",
    )

    if Config.FETCH_ON_STARTUP:
        run_update_cycle()

    start_scheduler()

    app = build_app(state, run_update_cycle)
    log.info("Serving on %s:%d", Config.HOST, Config.PORT)
    serve(app, host=Config.HOST, port=Config.PORT)


if __name__ == "__main__":
    main()
