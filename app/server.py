from __future__ import annotations

import os

from flask import Flask, Response, jsonify, send_file

from config import Config

PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta http-equiv="refresh" content="{refresh_seconds}">
<title>Front page</title>
<style>
  html, body {{
    margin: 0; padding: 0; width: 100%; height: 100%;
    background: #{bg_hex}; overflow: hidden;
  }}
  img {{
    display: block; margin: 0 auto;
    width: 100%; height: 100%; object-fit: contain;
  }}
</style>
</head>
<body>
  <img src="/current.png?ts={cache_bust}" alt="Front page">
</body>
</html>
"""


def build_app(state, trigger_update) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        s = state.get()
        cache_bust = s.get("last_success_at") or "0"
        html = PAGE_TEMPLATE.format(
            refresh_seconds=15 * 60,  # Kindle browser reloads every 15 min as a safety net
            bg_hex="ffffff",
            cache_bust=cache_bust,
        )
        return Response(html, mimetype="text/html")

    @app.get("/current.png")
    def current_image():
        if not os.path.exists(Config.CURRENT_IMAGE_PATH):
            return Response("No image generated yet", status=404)
        resp = send_file(Config.CURRENT_IMAGE_PATH, mimetype="image/png")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    @app.get("/status")
    def status():
        s = state.get()
        s["feeds"] = [name for name, _ in Config.RSS_FEEDS]
        s["update_times"] = Config.UPDATE_TIMES
        s["timezone"] = Config.TZ
        return jsonify(s)

    @app.get("/healthz")
    def healthz():
        return "ok", 200

    @app.post("/refresh")
    def refresh():
        """Manually trigger an update cycle (e.g. `curl -X POST .../refresh`)."""
        trigger_update()
        return jsonify(state.get())

    return app
