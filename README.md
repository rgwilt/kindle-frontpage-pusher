# kindle-frontpage-pusher

Turns your Kindle into a little newspaper stand. A Docker container pulls
headlines from a curated list of RSS feeds, lays them out as a
newspaper-style front page (masthead, columns, byline rules — not a plain
list), and renders it to a PNG sized exactly for your Kindle's screen. The
Kindle then just points its browser at the container and reloads
periodically.

Every refresh also picks a different page layout at random (a big lead
story with a grid below, a wide feature column with a sidebar, or a dense
three-column wire-service grid), so it doesn't look like the same template
re-filled with new text every time.

## How it works

1. On a schedule (`UPDATE_TIMES`, a few times a day by default), the
   container fetches the latest headlines from each feed in `RSS_FEEDS`.
2. Headlines are interleaved round-robin across sources (so no single feed
   dominates) and capped at `TOTAL_HEADLINES`.
3. The headlines are rendered directly with Pillow (no browser involved) into
   a newspaper-front-page-style PNG at your Kindle's exact resolution, using
   one of three randomly-chosen layouts.
4. The image is written to `/current.png`. The Kindle's browser, pointed at
   the container's `/` page, displays it full-screen and auto-reloads every
   15 minutes to pick up whatever the latest scheduled update produced.

A feed that fails to fetch (temporary outage, broken URL, etc.) is simply
skipped for that cycle — the digest renders from whatever feeds did
succeed. Only if every feed fails does the page keep showing the last
successful render.

## Quick start

```bash
git clone https://github.com/rgwilt/kindle-frontpage-pusher.git
cd kindle-frontpage-pusher/kindle-frontpage
cp .env.example .env
# edit .env if you want different feeds, update times, etc.
docker compose up -d --build
```

Then visit `http://<host>:8080/` in a browser to see the current digest, or
`http://<host>:8080/current.png` for the raw image.

## Configuration

All configuration is via environment variables (see `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `RSS_FEEDS` | BBC News, BBC World, Sky News, NPR | Comma-separated `Name\|https://feed-url` pairs. Add, remove, or replace feeds freely — any standard RSS/Atom feed works. |
| `HEADLINES_PER_FEED` | `5` | Max headlines pulled from each individual feed. |
| `TOTAL_HEADLINES` | `18` | Overall cap after interleaving across feeds. This is a pool to choose from, not a hard target — the layout engine drops whatever doesn't physically fit on the page, so it's fine for this to exceed what actually renders. |
| `PAPER_NAME` | `THE KINDLE TIMES` | Masthead title at the top of the page. |
| `UPDATE_TIMES` | `07:00,13:00,19:00` | 24h `HH:MM` times (in `TZ`) at which to refresh the digest. Add/remove entries to change frequency. |
| `TZ` | `Europe/London` | Timezone for `UPDATE_TIMES` and scheduling. |
| `KINDLE_WIDTH` / `KINDLE_HEIGHT` | `1264` / `1680` | Output image size in pixels. Defaults match the Kindle Paperwhite (2024), 7", 300ppi. |
| `HOST_PORT` | `8080` | Port exposed on the Docker host — change if it's already taken. |
| `FETCH_ON_STARTUP` | `true` | Run an update cycle immediately on container start, so `/current.png` isn't empty while waiting for the first scheduled time. |
| `LOG_LEVEL` | `INFO` | Python logging level. |

### Choosing feeds

Any standard RSS/Atom feed works. A few reliable general-news ones to try:

- BBC News: `http://feeds.bbci.co.uk/news/rss.xml`
- BBC World: `https://feeds.bbci.co.uk/news/world/rss.xml`
- Sky News: `https://feeds.skynews.com/feeds/rss/home.xml`
- NPR: `https://feeds.npr.org/1001/rss.xml`

Mix in whatever topics or outlets you like (tech, sport, a specific
publication's feed, etc.) — just keep the `Name|url` format and separate
entries with commas.

## Endpoints

- `GET /` — HTML page displaying the current digest full-screen, auto-reloading every 15 minutes. Point the Kindle's browser here.
- `GET /current.png` — the raw rendered PNG.
- `GET /status` — JSON with last attempt/success times, headlines used, sources used, any failed feeds, configured feeds, update schedule.
- `GET /healthz` — liveness check for Docker's `HEALTHCHECK`.
- `POST /refresh` — manually trigger an update cycle outside the schedule (e.g. `curl -X POST http://<host>:8080/refresh`).

## Deploying with Portainer

If you're running Portainer, you can deploy this as a stack without needing
Docker CLI access on the host.

**Option A — Repository (recommended if this repo is on GitHub):**

1. Stacks → Add stack → Build method: **Repository**.
2. Repository URL: `https://github.com/rgwilt/kindle-frontpage-pusher`
3. Repository reference: `refs/heads/main` (or whichever branch)
4. Compose path: `kindle-frontpage/docker-compose.yml`
5. Add any environment variable overrides you want under "Environment variables" (or leave blank to use the defaults baked into `docker-compose.yml`).
6. Deploy the stack.

**Option B — Web editor:**

1. Stacks → Add stack → Build method: **Web editor**.
2. Paste the contents of `docker-compose.yml` directly.
3. Since there's no repository context for `build: .` to pull `app/` from in this mode, use Option A or C instead if you need to build from source — the Web editor method only works well if you're pointing `image:` at an already-built image rather than building from local context.

**Option C — Upload:**

1. Zip up the `kindle-frontpage/` folder (with `Dockerfile`, `docker-compose.yml`, `app/`, `requirements.txt`) and upload it via Stacks → Add stack → Build method: **Upload**.

For any option, if port `8080` is already in use on your host, set
`HOST_PORT` to something else (e.g. `8787`) in the stack's environment
variables.

### Updating the stack after a code change

Since `docker-compose.yml` uses `pull_policy: build`, Portainer will rebuild
the image from source rather than trying to pull `kindle-frontpage-pusher`
from Docker Hub. After pulling/uploading updated files, redeploy the stack
(Portainer will offer to pull the latest repo content and rebuild).

## Getting it onto the Kindle's screen

The simplest and most robust option — and the one this project targets by
default — is the Kindle's built-in web browser: open it, navigate to
`http://<host>:8080/`, and leave it open. The page auto-reloads every 15
minutes, well within the `UPDATE_TIMES` cadence, so it'll always pick up the
latest digest.

### Alternative: push via FBInk (jailbroken Kindles)

If your Kindle is jailbroken and has FBInk available, `kindle-side/kindle-puller.sh`
is a small script that polls `/current.png` and draws it directly to the
framebuffer (no browser needed, so it also works from a cron-style
scheduler if your jailbreak has one):

```bash
#!/bin/sh
# see kindle-side/kindle-puller.sh for the full script
wget -q -O /tmp/current.png "http://<host>:8080/current.png"
fbink -g file=/tmp/current.png -c -d
```

As of writing, if your Kindle is running the **Véra** jailbreak, note that
its tooling ecosystem is still very new — there isn't yet an official
scheduler/cron package to run this script automatically, so the browser
approach above is the more practical path until that matures. Check
[kindlemodding.org](https://kindlemodding.org) for current tooling status.

## Notes

- A feed failing (timeout, HTTP error, malformed XML) doesn't take down the
  whole digest — it's just skipped for that cycle, and `/status` will show
  it under `failed_feeds`.
- Rendering is done entirely with Pillow — no headless browser, no
  JavaScript rendering, so the container image stays small and builds
  quickly.
