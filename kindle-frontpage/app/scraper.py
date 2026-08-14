"""
Scraper for frontpages.com

Earlier versions of this module read the <meta property="og:image"> tag on
each newspaper's page (https://www.frontpages.com/{slug}/) and downloaded
that URL directly with plain HTTP requests. That reliably 404'd -- even
from a second, independent fetcher -- because the page's actual cover image
is loaded client-side via JavaScript (the raw HTML ships an empty
<img src="">), and the og:image meta tag doesn't reliably match whatever
the page really loads.

Instead, we drive a real (headless) Chromium browser via Playwright to load
the page properly, then screenshot the rendered front-page <img> element
directly. Whatever image the browser actually displays is exactly what we
capture -- there's no separate "guess the CDN URL" step to get wrong.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

log = logging.getLogger("frontpage.scraper")

BASE_URL = "https://www.frontpages.com"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
NAV_TIMEOUT_MS = 30_000
IMAGE_TIMEOUT_MS = 20_000
CONSENT_TIMEOUT_MS = 5_000

# The site renders each front page as <img alt="Cover <Name> <date>" ...>.
COVER_IMAGE_SELECTOR = "img[alt^='Cover']"

# Every fetch starts a fresh browser context (no saved cookies), so the
# site's cookie-consent dialog (a Quantcast-style CMP: "frontpages.com asks
# for your consent" / "Consent and continue") shows up every time and
# visually sits on top of the front page image -- a screenshot of the image
# element still picks up whatever's rendered over it. Dismiss it first.
CONSENT_BUTTON_PATTERN = re.compile(
    r"consent and continue|accept all|accept cookies|^accept$|^agree$|^allow all$", re.I
)


def _dismiss_cookie_consent(page) -> None:
    """Best-effort click of a cookie-consent "accept" button, if one is showing."""
    candidates = [page] + list(page.frames)
    for frame in candidates:
        try:
            button = frame.get_by_role("button", name=CONSENT_BUTTON_PATTERN).first
            button.click(timeout=CONSENT_TIMEOUT_MS)
            page.wait_for_timeout(500)  # let the dialog's dismiss animation finish
            log.info("Dismissed a cookie-consent dialog")
            return
        except PlaywrightTimeoutError:
            continue
        except Exception:  # noqa: BLE001 - any frame/selector oddity, just move on
            continue
    log.info("No cookie-consent dialog found (or it was already dismissed)")


class ScrapeError(RuntimeError):
    """Raised when a newspaper's front page can't be found or captured."""


@dataclass
class FrontPage:
    slug: str
    name: str
    image_bytes: bytes


def fetch_front_page(slug: str) -> FrontPage:
    """Render today's front page for a given frontpages.com slug and screenshot it."""
    page_url = f"{BASE_URL}/{slug.strip('/')}/"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        try:
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1300, "height": 1900},
            )
            # A common headless-detection signal; harmless if the site doesn't check it.
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = context.new_page()

            log.info("Loading %s", page_url)
            try:
                page.goto(page_url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                # Some pages never go fully idle (ads/analytics keep polling);
                # falling back to "load" is good enough.
                try:
                    page.wait_for_load_state("load", timeout=NAV_TIMEOUT_MS)
                except PlaywrightTimeoutError as e:
                    raise ScrapeError(f"{slug}: page never finished loading ({page_url})") from e

            _dismiss_cookie_consent(page)

            locator = page.locator(COVER_IMAGE_SELECTOR).first
            try:
                locator.wait_for(state="visible", timeout=IMAGE_TIMEOUT_MS)
            except PlaywrightTimeoutError as e:
                raise ScrapeError(
                    f"{slug}: front page image never appeared on {page_url}"
                ) from e

            name = locator.get_attribute("alt") or slug
            image_bytes = locator.screenshot(type="png")
            if not image_bytes:
                raise ScrapeError(f"{slug}: screenshot came back empty")

            log.info("Captured front page image for '%s' (%s)", slug, name)
            return FrontPage(slug=slug, name=name, image_bytes=image_bytes)
        finally:
            browser.close()
