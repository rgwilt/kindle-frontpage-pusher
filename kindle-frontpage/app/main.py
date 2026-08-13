from __future__ import annotations

import logging
import sys

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from waitress import serve

from config import Config
from image_processor import process_front_page
from scraper import ScrapeError, fetch_front_page
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
    """Advance the rotation and try to fetch+process+save a fresh front page.

    If a given newspaper fails (page missing, image 404, etc.) we move on to
    the next one in the list, up to MAX_ATTEMPTS_PER_CYCLE tries, so one
    broken slug doesn't stall the whole rotation.
    """
    papers = Config.NEWSPAPERS
    if not papers:
        log.error("NEWSPAPERS list is empty; nothing to fetch")
        return

    state.record_attempt()
    index = state.next_index(len(papers))
    last_error = None

    for attempt in range(min(Config.MAX_ATTEMPTS_PER_CYCLE, len(papers))):
        idx = (index + attempt) % len(papers)
        slug = papers[idx]
        try:
            log.info("Update cycle: trying '%s' (rotation index %d)", slug, idx)
            front_page = fetch_front_page(slug)
            processed = process_front_page(
                front_page.image_bytes,
                width=Config.KINDLE_WIDTH,
                height=Config.KINDLE_HEIGHT,
                fit=Config.IMAGE_FIT,
                background=Config.BACKGROUND,
                contrast=Config.CONTRAST,
                sharpen=Config.SHARPEN,
            )
            with open(Config.CURRENT_IMAGE_PATH, "wb") as f:
                f.write(processed)
            state.record_success(slug, front_page.name, idx, len(papers))
            log.info("Update cycle succeeded with '%s'", slug)
            return
        except ScrapeError as e:
            log.warning("Failed to fetch '%s': %s", slug, e)
            last_error = str(e)
        except Exception as e:  # noqa: BLE001 - log and try the next paper
            log.exception("Unexpected error processing '%s'", slug)
            last_error = f"{slug}: {e}"

    log.error("Update cycle failed after %d attempt(s); keeping previous image", attempt + 1)
    state.record_error(last_error or "unknown error")


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
        "Starting kindle-frontpage-pusher: %d newspaper(s), %dx%d target, updates at %s (%s)",
        len(Config.NEWSPAPERS), Config.KINDLE_WIDTH, Config.KINDLE_HEIGHT,
        ", ".join(Config.UPDATE_TIMES), Config.TZ,
    )

    if Config.FETCH_ON_STARTUP:
        run_update_cycle()

    start_scheduler()

    app = build_app(state, run_update_cycle)
    log.info("Serving on %s:%d", Config.HOST, Config.PORT)
    serve(app, host=Config.HOST, port=Config.PORT)


if __name__ == "__main__":
    main()
