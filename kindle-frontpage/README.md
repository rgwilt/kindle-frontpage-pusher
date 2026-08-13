# kindle-frontpage-pusher

Docker container that pulls today's front page from [frontpages.com](https://www.frontpages.com),
processes it for a Kindle Paperwhite (2024, 7", 1264x1680 px, 300 ppi,
E Ink Carta 1300), and serves it over HTTP for the Kindle to pull.

## How it works

```
 ┌─────────────────────────┐        HTTP GET /current.png        ┌───────────────┐
 │ Docker container         │ <─────────────────────────────────  │ Kindle         │
 │  - scrapes frontpages.com│                                     │ (jailbroken)   │
 │  - rotates through your  │  cron/KUAL job runs kindle-puller.sh│ wget + FBInk   │
 │    newspaper list        │ ─────────────────────────────────>  │ draws the PNG  │
 │  - resizes/contrasts for │        serves current.png            │ full-screen    │
 │    the Kindle's screen   │                                     │                │
 └─────────────────────────┘                                     └───────────────┘
```

The container does **not** need any credentials or network access to the
Kindle itself. It just runs a tiny web server; something on the Kindle side
(a cron job calling `kindle-puller.sh`, included here) polls it and draws
whatever the latest image is with FBInk. This means the container works
even if the Kindle is asleep or off Wi-Fi most of the time — it'll just pick
up the latest image next time it wakes and polls.

Each scheduled update advances a rotation through your configured newspaper
list (one paper shown at a time, cycling back to the start), so over a few
updates you'll see each paper in turn rather than the same one every day.

## Quick start

```sh
cp .env.example .env
# edit .env: set NEWSPAPERS, UPDATE_TIMES, TZ if needed
docker compose up -d --build
```

Then check it worked:

```sh
curl http://localhost:8080/status
curl -o test.png http://localhost:8080/current.png
```

Open `http://<host>:8080/` in a browser to see the current front page
rendered full-screen (this is also usable directly as the Kindle browser's
home page if you'd rather not use FBInk — see below).

## Deploying with Portainer

`docker-compose.yml` builds its own image (`build: .`) and stores state in a
named volume (`kindle_frontpage_data`), so it works with any of Portainer's
three "Add stack" methods — but which one you use determines whether
Portainer can actually build the image itself.

### Option A — Git repository (recommended)

This is the only method where Portainer has the full build context (Python
source, `Dockerfile`, etc.) automatically, and it gets you one-click
redeploys via a webhook if you ever push changes.

1. Push this project's contents to a Git repo (GitHub, GitLab, Gitea,
   a self-hosted server — anything Portainer's host can reach).
2. In Portainer: **Stacks → Add stack → Repository**.
3. Fill in the repository URL, the branch (e.g. `refs/heads/main`), and
   the compose path (`docker-compose.yml`).
4. Under **Environment variables**, add any overrides you want (see the
   table below — same names as `.env.example`). Leave any you don't need
   unset; the compose file's defaults will apply.
5. Deploy the stack. Portainer clones the repo and builds the image via the
   `Dockerfile`.
6. Optionally enable the stack's webhook so a future `git push` triggers a
   redeploy automatically.

### Option B — Build in the Portainer UI, no Git/SSH needed

If you don't want to stand up a Git repo, Portainer can build the image
straight from files you upload in the browser:

1. **Images → Build a new image**, "Web editor" tab.
2. Paste the contents of this project's `Dockerfile`, then use **Select
   files** to also upload `requirements.txt` and everything under `app/`
   (keeping the same relative paths/filenames — Portainer needs them
   alongside the Dockerfile to satisfy the `COPY` instructions).
3. Name the image `kindle-frontpage-pusher:latest` and build it.
4. **Stacks → Add stack → Web editor**, paste `docker-compose.yml`, but
   delete the `build: .` line (there's no build context here, just the
   image you built in step 3 — compose will use the local image without
   trying to pull it).
5. Add environment variable overrides in the stack's **Environment
   variables** section, then deploy.

### Option C — Build over SSH, deploy via Web editor

If you have terminal access to the Docker host Portainer manages:

```sh
# on the Docker host
git clone <your-repo> kindle-frontpage   # or scp the project folder over
cd kindle-frontpage
docker build -t kindle-frontpage-pusher:latest .
```

Then follow steps 4-5 from Option B.

### Notes for any option

- The `data/` volume is a named Docker volume (`kindle_frontpage_data`),
  not a bind mount, so it works the same way regardless of which stack
  method you use or where Portainer happens to store the stack's files.
  You can browse/inspect it under Portainer's **Volumes** page.
- `HOST_PORT` (default `8080`) controls the port published on the Docker
  host — set it in the stack's environment variables if `8080` is already
  taken.
- After deploying, check `http://<host>:<HOST_PORT>/status` to confirm it's
  fetching successfully before wiring up `kindle-puller.sh` on the Kindle.

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `NEWSPAPERS` | a mix of US/UK papers | Comma-separated frontpages.com slugs, rotation order. Get a slug from the URL of `https://www.frontpages.com/<slug>/`. |
| `UPDATE_TIMES` | `07:00,13:00,19:00` | 24h `HH:MM` times (in `TZ`) at which to advance the rotation and fetch a fresh image. Add/remove entries to change how often it updates. |
| `TZ` | `Europe/London` | Timezone for `UPDATE_TIMES`. |
| `KINDLE_WIDTH` / `KINDLE_HEIGHT` | `1264` / `1680` | Target resolution. Matches the Kindle Paperwhite (2024) panel; change if you use this on a different device. |
| `IMAGE_FIT` | `contain` | `contain` shows the whole page, letterboxed; `cover` fills the screen and may crop edges. |
| `BACKGROUND` | `white` | Letterbox color for `contain` mode. |
| `CONTRAST` / `SHARPEN` | `1.15` / `true` | Extra contrast boost and unsharp-mask sharpening for crisper text on Carta 1300. |
| `MAX_ATTEMPTS_PER_CYCLE` | `3` | If a paper's page/image fails to fetch, try up to this many more papers in rotation order before giving up for that cycle. |
| `HOST_PORT` | `8080` | Port published on the Docker host (container always listens on 8080 internally). |

## Endpoints

- `GET /current.png` — the latest processed front page, exactly `KINDLE_WIDTH`x`KINDLE_HEIGHT`.
- `GET /` — a minimal full-screen HTML viewer (auto-refreshes every 15 min); usable directly as a Kindle browser home page.
- `GET /status` — JSON: current paper, last success/error time, rotation list, schedule.
- `GET /healthz` — for the container's `HEALTHCHECK` / your own monitoring.
- `POST /refresh` — trigger an update cycle immediately (handy for testing: `curl -X POST http://localhost:8080/refresh`).

## Getting it onto the Kindle's screen

Since delivery is HTTP pull, something on the Kindle needs to fetch
`/current.png` and draw it. `kindle-side/kindle-puller.sh` does this with
[FBInk](https://github.com/NiLuJe/FBInk) (very commonly available on
jailbroken Kindles) — it downloads the image and, if it's changed since the
last poll, redraws the screen.

1. Copy `kindle-side/kindle-puller.sh` onto the Kindle (e.g. `/mnt/us/kindle-puller.sh`) via USB, `scp`, or however you push files to it.
2. Edit `SERVER_URL` at the top of the script to point at the machine running this container (e.g. `http://192.168.1.10:8080/current.png`).
3. Make it executable: `chmod +x /mnt/us/kindle-puller.sh`.
4. Register it as a periodic job using whatever cron/task mechanism your jailbreak provides — most setups have a KUAL "Extensions" / cron package that lets you add a line like:
   ```
   */15 * * * *  /mnt/us/kindle-puller.sh
   ```
   Polling every 10-15 minutes is cheap (one HTTP GET) and the script only
   redraws the screen when the image actually changed, so it won't flash
   the display needlessly.
5. If your jailbreak doesn't have FBInk installed, install it first (it's a
   standard "extra" on most 2024-era jailbreak toolchains) — or, as a
   fallback with no FBInk dependency, point the Kindle's experimental
   browser at `http://<host>:8080/` and leave it open; the page
   auto-refreshes every 15 minutes on its own.

## Manually finding a newspaper's slug

Browse to `https://www.frontpages.com/`, click through to the paper you
want, and copy the segment of the URL between the slashes, e.g.
`https://www.frontpages.com/the-guardian/` → `the-guardian`. Not every paper
listed on the homepage has a page that stays up permanently — if one
disappears, `/status` will show the error and the rotation will just skip
past it (via `MAX_ATTEMPTS_PER_CYCLE`) until you update `NEWSPAPERS`.

## Notes

- This scrapes a public page a handful of times a day (per `UPDATE_TIMES`)
  — please keep the frequency reasonable and check frontpages.com's terms
  of use if you plan to run this somewhere with heavier traffic.
- All state (rotation position, last error, current image) lives in
  `./data`, mounted as a volume, so it survives container restarts.
