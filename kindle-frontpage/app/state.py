"""Small JSON-file-backed state: which newspaper we're on, and last results."""
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
            "rotation_index": 0,
            "current_slug": None,
            "current_name": None,
            "last_success_at": None,
            "last_error": None,
            "last_attempt_at": None,
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

    def next_index(self, list_length: int) -> int:
        """Return the rotation index to use next, wrapped to list_length."""
        with _lock:
            if list_length <= 0:
                return 0
            idx = self._data.get("rotation_index", 0) % list_length
            return idx

    def record_attempt(self) -> None:
        with _lock:
            self._data["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def record_success(self, slug: str, name: str, index_used: int, list_length: int) -> None:
        with _lock:
            self._data["current_slug"] = slug
            self._data["current_name"] = name
            self._data["last_success_at"] = datetime.now(timezone.utc).isoformat()
            self._data["last_error"] = None
            if list_length > 0:
                self._data["rotation_index"] = (index_used + 1) % list_length
            self._save()

    def record_error(self, message: str) -> None:
        with _lock:
            self._data["last_error"] = message
            self._save()
