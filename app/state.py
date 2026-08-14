"""Small JSON-file-backed state: last digest results."""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict

log = logging.getLogger("frontpage.state")

_lock = threading.Lock()


class State:
    def __init__(self, path: str):
        self.path = path
        self._data: Dict[str, Any] = {
            "headlines_used": 0,
            "sources_used": [],
            "failed_feeds": [],
            "last_success_at": None,
            "last_error": None,
            "last_attempt_at": None,
            "now_reading": None,
        }
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data.update(json.load(f))
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Could not read state file %s (%s); starting fresh", self.path, e)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp_path, self.path)

    def get(self) -> Dict[str, Any]:
        with _lock:
            return dict(self._data)

    def record_attempt(self) -> None:
        with _lock:
            self._data["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def record_success(
        self, headlines_used: int, sources_used: list, failed_feeds: list, now_reading: str | None = None
    ) -> None:
        with _lock:
            self._data["headlines_used"] = headlines_used
            self._data["sources_used"] = sources_used
            self._data["failed_feeds"] = failed_feeds
            self._data["now_reading"] = now_reading
            self._data["last_success_at"] = datetime.now(timezone.utc).isoformat()
            self._data["last_error"] = None
            self._save()

    def record_error(self, message: str) -> None:
        with _lock:
            self._data["last_error"] = message
            self._save()
