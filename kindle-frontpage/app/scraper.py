"""
Scraper for frontpages.com

Each newspaper has a page at https://www.frontpages.com/{slug}/ whose
<meta property="og:image"> tag points at today's front-page scan, e.g.:

    https://www.frontpages.com/g/2026/08/12/the-new-york-times-070018s30.webp.jpg

We fetch that page, pull the og:image URL out of it, and download the image.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("frontpage.scraper")

BASE_URL = "https://www.frontpages.com"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "kindle-frontpage-pusher/1.0"
)
REQUEST_TIMEOUT = 20  # seconds


class ScrapeError(RuntimeError):
    """Raised when a newspaper's front page can't be found or downloaded."""


@dataclass
class FrontPage:
    slug: str
    name: str
    image_url: str
    image_bytes: bytes


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-GB,en;q=0.9"})
    return s


def fetch_front_page(slug: str) -> FrontPage:
    """Fetch today's front page image for a given frontpages.com slug."""
    page_url = urljoin(BASE_URL + "/", f"{slug.strip('/')}/")
    sess = _session()

    log.info("Fetching newspaper page: %s", page_url)
    resp = sess.get(page_url, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        raise ScrapeError(f"{slug}: page returned HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")

    og_image = soup.find("meta", property="og:image")
    if not og_image or not og_image.get("content"):
        raise ScrapeError(f"{slug}: could not find og:image meta tag on {page_url}")
    image_url = og_image["content"]

    title_tag = soup.find("meta", property="og:title") or soup.find("title")
    name = title_tag.get("content") if title_tag and title_tag.get("content") else (
        title_tag.text.strip() if title_tag else slug
    )

    log.info("Downloading front page image: %s", image_url)
    img_resp = sess.get(image_url, timeout=REQUEST_TIMEOUT)
    if img_resp.status_code != 200 or not img_resp.content:
        raise ScrapeError(f"{slug}: image download returned HTTP {img_resp.status_code}")

    return FrontPage(slug=slug, name=name, image_url=image_url, image_bytes=img_resp.content)
